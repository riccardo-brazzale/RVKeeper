import logging
from decimal import Decimal, ROUND_CEILING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from orders.models import Notification
from .models import (
    GoodsReceipt,
    JobPartUsage,
    GoodsReceiptLine,
    Part,
    PartMovement,
    PartSupplierOffer,
    PartsRequest,
    PurchaseOrder,
    PurchaseOrderDemand,
    PurchaseOrderLine,
    SupplierPriceListItem,
    TransferSlip,
    TransferSlipLine,
)


logger = logging.getLogger(__name__)


class InsufficientStockError(Exception):
    """La quantità disponibile non basta per completare l'operazione richiesta."""


def round_order_quantity(quantity, minimum, package_multiple):
    quantity = Decimal(quantity)
    minimum = Decimal(minimum)
    package_multiple = Decimal(package_multiple)
    if quantity <= 0 or minimum <= 0 or package_multiple <= 0:
        raise ValueError("Quantità, minimo e multiplo confezione devono essere positivi.")
    required_packages = (quantity / package_multiple).to_integral_value(rounding=ROUND_CEILING)
    minimum_packages = (minimum / package_multiple).to_integral_value(rounding=ROUND_CEILING)
    return max(required_packages, minimum_packages) * package_multiple


def supplier_price_for_date(part, supplier, effective_date):
    return (
        SupplierPriceListItem.objects.filter(
            price_list__workshop_id=part.workshop_id,
            price_list__supplier=supplier,
            price_list__is_active=True,
            price_list__valid_from__lte=effective_date,
        )
        .filter(
            Q(price_list__valid_to__isnull=True)
            | Q(price_list__valid_to__gte=effective_date)
        )
        .filter(
            Q(part=part)
            | Q(internal_article_code=part.part_number)
        )
        .select_related("price_list", "part")
        .order_by("-price_list__valid_from", "-pk")
        .first()
    )


def _transfer_slip_for(work_order, user):
    work_order = work_order.__class__.objects.select_for_update().get(pk=work_order.pk)
    slip, _ = TransferSlip.objects.get_or_create(
        work_order=work_order,
        defaults={"workshop_id": work_order.workshop_id, "created_by": user},
    )
    return slip


def reserve_parts_request(parts_request, *, user):
    """Impegna subito lo stock libero per una richiesta di ricambi."""
    with transaction.atomic():
        item = PartsRequest.objects.select_for_update(of=("self",)).select_related("work_order", "part").get(
            pk=parts_request.pk,
        )
        if item.part_id is None:
            return None
        work_order = item.work_order.__class__.objects.select_for_update().get(
            pk=item.work_order_id,
        )
        if work_order.status in ("completed", "cancelled"):
            raise ValidationError("L'ordine di lavoro è chiuso o annullato.")
        part = Part.objects.select_for_update().get(pk=item.part_id, workshop_id=item.workshop_id)
        slip = _transfer_slip_for(work_order, user)
        line = TransferSlipLine.objects.select_for_update().filter(parts_request=item).first()
        if line is None:
            line = TransferSlipLine(
                transfer_slip=slip,
                job_id=item.job_id,
                parts_request=item,
                part=part,
                quantity_requested=item.quantity_requested * item.conversion_factor,
            )
        else:
            line.quantity_requested = item.quantity_requested * item.conversion_factor

        reserved_elsewhere = TransferSlipLine.objects.filter(
            part=part,
            transfer_slip__status="open",
            status__in=("reserved", "waiting_stock"),
        ).exclude(pk=line.pk).aggregate(total=Sum("quantity_reserved"))["total"] or Decimal("0")
        available_for_line = max(Decimal("0"), part.quantity - reserved_elsewhere)
        line.quantity_reserved = min(line.quantity_requested, available_for_line)
        line.status = "reserved" if line.quantity_reserved == line.quantity_requested else "waiting_stock"
        line.save()

        logger.info(
            "Ricambio impegnato per ordine di lavoro",
            extra={
                "work_order_id": item.work_order_id,
                "activity_id": item.job_id,
                "part_id": part.pk,
                "user_id": user.pk,
                "quantity_requested": str(line.quantity_requested),
                "quantity_reserved": str(line.quantity_reserved),
            },
        )
        return line


def reserve_job_usage(job, quantities_by_part, *, user):
    """Impegna i ricambi aggiuntivi registrati alla fine della sessione."""
    with transaction.atomic():
        locked_job = job.__class__.objects.select_for_update().select_related("work_order").get(pk=job.pk)
        slip = _transfer_slip_for(locked_job.work_order, user)
        for part_id, quantity in sorted(quantities_by_part.items()):
            quantity = Decimal(quantity)
            if quantity <= 0:
                raise ValidationError("La quantità utilizzata deve essere maggiore di zero.")
            part = Part.objects.select_for_update().get(pk=part_id, workshop_id=locked_job.workshop_id)
            reserved = TransferSlipLine.objects.filter(
                part=part,
                transfer_slip__status="open",
                status__in=("reserved", "waiting_stock"),
            ).aggregate(total=Sum("quantity_reserved"))["total"] or Decimal("0")
            available = max(Decimal("0"), part.quantity - reserved)
            if quantity > available:
                raise InsufficientStockError(str(part))
            TransferSlipLine.objects.create(
                transfer_slip=slip,
                job=locked_job,
                part=part,
                quantity_requested=quantity,
                quantity_reserved=quantity,
                status="reserved",
            )


def close_transfer_slip(work_order, *, user):
    """Scarica gli impegni all'atto della chiusura dell'ordine di lavoro."""
    with transaction.atomic():
        work_order = work_order.__class__.objects.select_for_update().get(pk=work_order.pk)
        slip = TransferSlip.objects.select_for_update().filter(work_order=work_order).first()
        if slip is None or slip.status != "open":
            return slip
        lines = list(
            TransferSlipLine.objects.select_for_update(of=("self",))
            .filter(transfer_slip=slip, status__in=("reserved", "waiting_stock"))
            .select_related("part", "job")
            .order_by("part_id", "pk")
        )
        unfulfilled = [
            line for line in lines if line.quantity_reserved < line.quantity_requested
        ]
        if unfulfilled:
            parts = ", ".join(sorted({str(line.part) for line in unfulfilled}))
            raise InsufficientStockError(parts)
        part_ids = sorted({line.part_id for line in lines if line.quantity_reserved > 0})
        parts = {
            part.pk: part
            for part in Part.objects.select_for_update().filter(pk__in=part_ids).order_by("pk")
        }
        quantities = {}
        for line in lines:
            quantities[line.part_id] = quantities.get(line.part_id, Decimal("0")) + line.quantity_reserved
        insufficient = [
            parts[part_id] for part_id, quantity in quantities.items()
            if part_id not in parts or parts[part_id].quantity < quantity
        ]
        if insufficient:
            raise InsufficientStockError(", ".join(str(part) for part in insufficient))

        now = timezone.now()
        for line in lines:
            quantity = line.quantity_reserved
            if quantity <= 0:
                continue
            part = parts[line.part_id]
            part.quantity -= quantity
            part.save(update_fields=("quantity", "updated_at"))
            PartMovement.objects.create(
                workshop_id=slip.workshop_id,
                part=part,
                work_order=work_order,
                movement_type="out",
                quantity=quantity,
                unit_cost=part.cost_price,
                note=f"Scarico bolla di trasferimento #{slip.pk}",
                created_by=user,
            )
            if line.job_id and not line.parts_request_id:
                JobPartUsage.objects.create(
                    workshop_id=slip.workshop_id,
                    job_id=line.job_id,
                    part=part,
                    quantity_used=quantity,
                    used_by=user,
                )
            line.status = "consumed"
            line.save(update_fields=("status",))
        slip.status = "closed"
        slip.closed_at = now
        slip.save(update_fields=("status", "closed_at"))
        logger.info(
            "Bolla di trasferimento scaricata",
            extra={"work_order_id": work_order.pk, "transfer_slip_id": slip.pk, "user_id": user.pk},
        )
        return slip


def cancel_transfer_slip(work_order, *, user):
    """Libera le quantità impegnate quando un ordine viene annullato."""
    with transaction.atomic():
        work_order = work_order.__class__.objects.select_for_update().get(pk=work_order.pk)
        slip = TransferSlip.objects.select_for_update().filter(work_order=work_order).first()
        if slip is None or slip.status != "open":
            return slip
        lines = TransferSlipLine.objects.select_for_update().filter(transfer_slip=slip)
        lines.update(status="released", quantity_reserved=0)
        slip.status = "cancelled"
        slip.closed_at = timezone.now()
        slip.save(update_fields=("status", "closed_at"))
        logger.info(
            "Impegni ricambi rilasciati per annullamento ordine",
            extra={"work_order_id": work_order.pk, "transfer_slip_id": slip.pk, "user_id": user.pk},
        )
        return slip


def _next_purchase_order_number(workshop):
    prefix = f"OF-{timezone.localdate().year}-"
    latest = (
        PurchaseOrder.objects.filter(workshop=workshop, order_number__startswith=prefix)
        .order_by("-order_number")
        .values_list("order_number", flat=True)
        .first()
    )
    sequence = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{sequence:04d}"


def add_request_to_purchase_order(parts_request, *, user, effective_date=None):
    """Raggruppa una richiesta nell'ordine aperto del fornitore selezionato."""
    effective_date = effective_date or timezone.localdate()
    with transaction.atomic():
        item = PartsRequest.objects.select_for_update(of=("self",)).select_related(
            "part", "work_order", "supplier_offer",
        ).get(pk=parts_request.pk)
        if item.part_id is None:
            raise ValidationError("Una richiesta senza articolo di magazzino non può essere ordinata.")
        if item.work_order.status in ("completed", "cancelled"):
            raise ValidationError("Non è possibile ordinare ricambi per un ordine di lavoro chiuso.")
        if item.purchase_order_demands.exists():
            return item.purchase_order_demands.select_related(
                "purchase_order_line__purchase_order",
            ).first().purchase_order_line.purchase_order

        transfer_line = TransferSlipLine.objects.select_for_update(of=("self",)).filter(
            parts_request=item,
            status__in=("reserved", "waiting_stock"),
        ).first()
        if transfer_line is None:
            transfer_line = reserve_parts_request(item, user=user)
        required = item.quantity_requested * item.conversion_factor
        quantity_to_order = required - transfer_line.quantity_reserved
        if quantity_to_order <= 0:
            raise ValidationError("La quantità richiesta è già interamente impegnata in magazzino.")

        offers = list(
            PartSupplierOffer.objects.filter(part_id=item.part_id).select_related("supplier")
        )
        if item.supplier_offer_id:
            offer = next((candidate for candidate in offers if candidate.pk == item.supplier_offer_id), None)
            if offer is None:
                raise ValidationError("L'offerta selezionata non appartiene all'articolo richiesto.")
        else:
            if not offers:
                raise ValidationError("L'articolo non ha un fornitore associato.")
            offer = min(
                offers,
                key=lambda candidate: (
                    not candidate.is_preferred,
                    candidate.net_purchase_price,
                    candidate.supplier_id,
                ),
            )

        list_item = supplier_price_for_date(item.part, offer.supplier, effective_date)
        unit_price = list_item.unit_price if list_item else offer.purchase_price
        discount = list_item.discount_percent if list_item else offer.discount_percent
        ordered = round_order_quantity(
            quantity_to_order,
            offer.minimum_order_quantity,
            offer.package_multiple,
        )

        from workshops.models import Workshop

        workshop = Workshop.objects.select_for_update().get(pk=item.workshop_id)
        order = PurchaseOrder.objects.select_for_update().filter(
            workshop=workshop, supplier=offer.supplier, status="open",
        ).order_by("pk").first()
        if order is None:
            order = PurchaseOrder.objects.create(
                workshop=workshop,
                supplier=offer.supplier,
                order_number=_next_purchase_order_number(workshop),
                order_date=effective_date,
                created_by=user,
            )

        line = PurchaseOrderLine.objects.select_for_update().filter(
            purchase_order=order, part=item.part,
        ).first()
        if line is None:
            line = PurchaseOrderLine.objects.create(
                purchase_order=order,
                part=item.part,
                supplier_offer=offer,
                supplier_article_code=(
                    list_item.supplier_article_code if list_item else offer.supplier_code
                ),
                quantity_required=quantity_to_order,
                quantity_ordered=ordered,
                unit_price=unit_price,
                discount_percent=discount,
            )
        else:
            line.quantity_required += quantity_to_order
            line.quantity_ordered = round_order_quantity(
                line.quantity_required,
                offer.minimum_order_quantity,
                offer.package_multiple,
            )
            line.unit_price = unit_price
            line.discount_percent = discount
            line.save(update_fields=(
                "quantity_required", "quantity_ordered", "unit_price", "discount_percent",
            ))
        PurchaseOrderDemand.objects.create(
            purchase_order_line=line,
            parts_request=item,
            quantity_requested=quantity_to_order,
        )
        item.supplier_offer = offer
        item.supplier = str(offer.supplier)
        item.purchase_price = unit_price
        item.save(update_fields=("supplier_offer", "supplier", "purchase_price", "updated_at"))
        logger.info(
            "Richiesta ricambio aggiunta a ordine fornitore",
            extra={
                "work_order_id": item.work_order_id,
                "activity_id": item.job_id,
                "part_id": item.part_id,
                "purchase_order_id": order.pk,
                "supplier_id": offer.supplier_id,
                "user_id": user.pk,
            },
        )
        return order


def receive_purchase_order_line(purchase_order_line, quantity, *, user, receipt_number):
    """Registra una ricezione parziale e carica il magazzino in modo atomico."""
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValidationError("La quantità ricevuta deve essere maggiore di zero.")
    with transaction.atomic():
        line = PurchaseOrderLine.objects.select_for_update().select_related(
            "purchase_order", "part",
        ).get(pk=purchase_order_line.pk)
        if line.purchase_order.status in ("closed", "cancelled"):
            raise ValidationError("L'ordine fornitore è già chiuso o annullato.")
        remaining = line.quantity_ordered - line.quantity_received
        if quantity > remaining:
            raise ValidationError("La quantità ricevuta supera il residuo dell'ordine.")
        order = line.purchase_order
        part = Part.objects.select_for_update().get(pk=line.part_id)
        receipt, _ = GoodsReceipt.objects.get_or_create(
            workshop_id=order.workshop_id,
            purchase_order=order,
            receipt_number=receipt_number,
            defaults={"received_by": user},
        )
        receipt_line, created = GoodsReceiptLine.objects.get_or_create(
            goods_receipt=receipt,
            purchase_order_line=line,
            defaults={"quantity_received": quantity},
        )
        if not created:
            receipt_line.quantity_received += quantity
            receipt_line.save(update_fields=("quantity_received",))
        line.quantity_received += quantity
        line.save(update_fields=("quantity_received",))
        demand_quantity = quantity
        demands = list(
            PurchaseOrderDemand.objects.select_for_update()
            .filter(purchase_order_line=line)
            .select_related("parts_request")
            .order_by("pk")
        )
        for demand in demands:
            remaining_demand = demand.quantity_requested - demand.quantity_received
            allocated = min(remaining_demand, demand_quantity)
            if allocated <= 0:
                continue
            demand.quantity_received += allocated
            demand.save(update_fields=("quantity_received",))
            demand_quantity -= allocated
            if demand_quantity <= 0:
                break
        part.quantity += quantity
        part.save(update_fields=("quantity", "updated_at"))
        PartMovement.objects.create(
            workshop_id=order.workshop_id,
            part=part,
            movement_type="in",
            quantity=quantity,
            unit_cost=line.unit_price,
            note=f"Entrata bolla {receipt.receipt_number}",
            created_by=user,
        )
        remaining_lines = PurchaseOrderLine.objects.filter(
            purchase_order=order,
            quantity_received__lt=F("quantity_ordered"),
        ).exists()
        if remaining_lines:
            order.status = "partially_received"
            order.save(update_fields=("status",))
        else:
            order.status = "closed"
            order.closed_at = timezone.now()
            order.save(update_fields=("status", "closed_at"))
        _allocate_received_stock(part, user=user)
        for demand in demands:
            request_item = demand.parts_request
            transfer_line = TransferSlipLine.objects.filter(
                parts_request=request_item,
            ).first()
            reserved = transfer_line.quantity_reserved if transfer_line else Decimal("0")
            delivered = min(
                request_item.quantity_requested,
                reserved / request_item.conversion_factor,
            )
            PartsRequest.objects.filter(pk=request_item.pk).update(
                quantity_delivered=delivered,
                updated_at=timezone.now(),
            )
        logger.info(
            "Merce ricevuta da ordine fornitore",
            extra={
                "purchase_order_id": order.pk,
                "purchase_order_line_id": line.pk,
                "part_id": part.pk,
                "quantity_received": str(quantity),
                "user_id": user.pk,
            },
        )
        return receipt


def _allocate_received_stock(part, *, user):
    """Assegna il nuovo stock alle richieste in attesa, in ordine cronologico."""
    lines = list(
        TransferSlipLine.objects.select_for_update()
        .filter(
            part=part,
            transfer_slip__status="open",
            status="waiting_stock",
        )
        .select_related("transfer_slip")
        .order_by("created_at", "pk")
    )
    reserved_elsewhere = TransferSlipLine.objects.filter(
        part=part,
        transfer_slip__status="open",
        status__in=("reserved", "waiting_stock"),
    ).aggregate(total=Sum("quantity_reserved"))["total"] or Decimal("0")
    available = max(Decimal("0"), part.quantity - reserved_elsewhere)
    for line in lines:
        needed = line.quantity_requested - line.quantity_reserved
        reserved = min(needed, available)
        if reserved <= 0:
            break
        line.quantity_reserved += reserved
        available -= reserved
        line.status = "reserved" if line.quantity_reserved == line.quantity_requested else "waiting_stock"
        line.save(update_fields=("quantity_reserved", "status"))
        if line.parts_request_id and line.status == "reserved":
            request_item = line.parts_request
            PartsRequest.objects.filter(pk=request_item.pk).update(
                status="ready_for_pickup", updated_at=timezone.now(),
            )
            if request_item.requested_by_id:
                Notification.objects.create(
                    workshop_id=request_item.workshop_id,
                    user_id=request_item.requested_by_id,
                    title="Ricambio disponibile",
                    body=f"{request_item.work_order.ro_number} · {part}",
                    link="/lavori/miei/",
                    work_order=request_item.work_order,
                )
        logger.info(
            "Ricambio ricevuto e impegnato per richiesta",
            extra={
                "work_order_id": line.transfer_slip.work_order_id,
                "activity_id": line.job_id,
                "part_id": part.pk,
                "parts_request_id": line.parts_request_id,
                "user_id": user.pk,
                "quantity_reserved": str(reserved),
            },
        )
