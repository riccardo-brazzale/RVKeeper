import csv
import io
import logging
import os
from zipfile import BadZipFile
from decimal import Decimal, InvalidOperation
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models, transaction
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from clientandsuppliers.models import CamperOwner
from workshops.models import Membership
from orders.models import AuditLog, Notification, PriceList, PriceListItem, WorkOrder
from .documents import goods_receipt_pdf, purchase_order_pdf
from .models import (
    GoodsReceipt,
    Part,
    PartDocument,
    PartMovement,
    PartSupplierOffer,
    PartsRequest,
    PurchaseOrder,
    PurchaseOrderLine,
    SupplierPriceList,
    SupplierPriceListItem,
)
from .forms import (
    PartDocumentForm,
    PartForm,
    PurchaseOrderForm,
    PurchaseOrderLineFormSet,
    PartSupplierOfferForm,
)
from .services import receive_purchase_order_line


logger = logging.getLogger(__name__)


def _active_workshop(user):
    membership = Membership.objects.filter(user=user, is_active=True, workshop__is_active=True).select_related("workshop").first()
    return membership.workshop if membership else None


def _workshop_or_redirect(request):
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, _("Your account is not associated with an active workshop."))
    return workshop


def _is_mechanic(user):
    return getattr(user, "profile", "") == "mechanic"


def _deny_mechanic(request):
    if _is_mechanic(request.user):
        return HttpResponseForbidden(_("The parts catalog and purchasing are managed by a supervisor."))
    return None


def _audit(workshop, user, action, part, details=""):
    AuditLog.objects.create(workshop=workshop, actor=user, action=action, entity_type=Part.__name__,
                            entity_id=str(part.pk), details=details or str(part))


@login_required
def inventory(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    is_mechanic = _is_mechanic(request.user)
    parts = Part.objects.filter(workshop=workshop)
    query = request.GET.get("q", "").strip()
    if query:
        parts = parts.filter(models.Q(part_number__icontains=query) | models.Q(name__icontains=query) |
                             models.Q(description__icontains=query) | models.Q(location__icontains=query) |
                             models.Q(supplier_offers__supplier_code__istartswith=query) |
                             models.Q(supplier_offers__supplier_code__iexact=query) |
                             models.Q(supplier_price_list_items__supplier_article_code__istartswith=query) |
                             models.Q(supplier_price_list_items__supplier_article_code__iexact=query)).distinct()
    low_stock = parts.filter(quantity__lte=models.F("min_stock"))
    for part in low_stock.iterator():
        Notification.objects.get_or_create(
            workshop=workshop, user=None, title=_("Low parts stock"), link="/magazzino/", read=False,
            defaults={"body": f"{part.part_number} · {part.name}: disponibili {part.quantity}, minimo {part.min_stock}"},
        )
    page_obj = Paginator(parts.select_related("article_class", "article_group").order_by("name", "pk"), 50).get_page(
        request.GET.get("page")
    )
    return render(request, "parts/part_list.html", {
        "parts": page_obj,
        "page_obj": page_obj,
        "query": query,
        "low_stock_count": low_stock.count(),
        "is_mechanic": is_mechanic,
    })


@login_required
def part_create(request):
    if denied := _deny_mechanic(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    form = PartForm(request.POST or None, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        part = form.save(commit=False)
        part.workshop = workshop
        part.save()
        _audit(workshop, request.user, "create", part)
        messages.success(request, _("Part created. Record a movement to add initial stock."))
        return redirect("part_detail", pk=part.pk)
    return render(request, "parts/part_form.html", {"form": form, "title": _("New part")})


@login_required
def part_edit(request, pk):
    if denied := _deny_mechanic(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    part = get_object_or_404(Part, pk=pk, workshop=workshop)
    form = PartForm(request.POST or None, instance=part, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        part = form.save()
        _audit(workshop, request.user, "update", part)
        messages.success(request, _("Part details updated."))
        return redirect("part_detail", pk=part.pk)
    return render(request, "parts/part_form.html", {"form": form, "title": _("Edit part"), "part": part})


@login_required
def part_detail(request, pk):
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    is_mechanic = _is_mechanic(request.user)
    part = get_object_or_404(Part, pk=pk, workshop=workshop)
    price_rows = []
    if not is_mechanic:
        if request.method == "POST":
            changed_count = 0
            with transaction.atomic():
                for key, value in request.POST.items():
                    if not key.startswith("current_") and not key.startswith("future_"):
                        continue
                    field, list_id = key.rsplit("_", 1)
                    try:
                        price_list = PriceList.objects.get(
                            pk=int(list_id),
                            workshop=workshop,
                            customer__isnull=True,
                        )
                    except (PriceList.DoesNotExist, ValueError, TypeError):
                        continue
                    raw = value.strip().replace(",", ".")
                    try:
                        price = Decimal(raw) if raw else None
                    except (InvalidOperation, TypeError):
                        continue
                    if price is not None and price < 0:
                        continue
                    item, _ = PriceListItem.objects.get_or_create(
                        price_list=price_list,
                        part=part,
                        defaults={
                            "valid_from": price_list.current_valid_from,
                            "unit_price": Decimal("0"),
                        },
                    )
                    if field == "current":
                        if price is None:
                            continue
                        item.unit_price = price
                        item.valid_from = price_list.current_valid_from
                        changed_count += 1
                    else:
                        item.future_price = price
                        item.future_valid_from = price_list.future_valid_from
                        changed_count += 1
                    item.full_clean()
                    item.save()
            if changed_count:
                messages.success(request, _("Part prices updated."))
            return redirect("part_detail", pk=part.pk)

        price_lists = PriceList.objects.filter(
            workshop=workshop,
            is_active=True,
            customer__isnull=True,
        ).annotate(
            has_item=models.Exists(
                PriceListItem.objects.filter(price_list=models.OuterRef("pk"), part=part)
            )
        ).order_by("-is_default", "-is_workshop", "name", "code")
        items = {
            item.price_list_id: item
            for item in PriceListItem.objects.filter(price_list__in=price_lists, part=part)
        }
        for price_list in price_lists:
            price_rows.append({
                "price_list": price_list,
                "item": items.get(price_list.pk),
            })
    return render(request, "parts/part_detail.html", {
        "part": part,
        "documents": part.documents.select_related("uploaded_by", "category"),
        "is_mechanic": is_mechanic,
        "price_rows": price_rows,
    })


@login_required
def part_movement(request, pk):
    if denied := _deny_mechanic(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    part = get_object_or_404(Part, pk=pk, workshop=workshop)
    orders = WorkOrder.objects.filter(workshop=workshop).exclude(status__in=("completed", "cancelled"))
    if request.method == "POST":
        try:
            qty = Decimal(request.POST.get("quantity", ""))
            kind = request.POST.get("movement_type")
            if qty < 0 or (kind != "adjustment" and qty == 0) or kind not in ("in", "out", "adjustment"):
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            messages.error(request, _("Enter a valid quantity and movement type."))
            return redirect("part_movement", pk=part.pk)
        with transaction.atomic():
            locked = Part.objects.select_for_update().get(pk=part.pk, workshop=workshop)
            delta = qty if kind == "in" else -qty
            if kind == "adjustment":
                delta = qty - locked.quantity
            if locked.quantity + delta < 0:
                messages.error(request, _("Stock cannot be negative."))
                return redirect("part_movement", pk=part.pk)
            order_id = request.POST.get("work_order") or None
            order = get_object_or_404(orders, pk=order_id) if order_id else None
            locked.quantity += delta
            locked.save(update_fields=("quantity", "updated_at"))
            PartMovement.objects.create(workshop=workshop, part=locked, work_order=order,
                movement_type=kind, quantity=delta if kind == "adjustment" else qty,
                unit_cost=locked.cost_price, note=request.POST.get("note", "").strip(), created_by=request.user)
            _audit(workshop, request.user, "stock_" + kind, locked, f"Variazione {delta} {locked.unit}")
        messages.success(request, _("Inventory movement recorded."))
        return redirect("inventory")
    return render(request, "parts/part_movement.html", {
        "part": part, "orders": orders, "movements": part.movements.select_related("work_order", "created_by")[:30],
    })


@login_required
def part_supplier_offer(request, part_pk, offer_pk=None):
    if denied := _deny_mechanic(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    part = get_object_or_404(Part, pk=part_pk, workshop=workshop)
    instance = get_object_or_404(PartSupplierOffer, pk=offer_pk, part=part) if offer_pk else None
    form = PartSupplierOfferForm(request.POST or None, instance=instance, workshop=workshop, part=part)
    if request.method == "POST" and form.is_valid():
        offer = form.save(commit=False)
        offer.part = part
        offer.full_clean()
        with transaction.atomic():
            locked_part = Part.objects.select_for_update().get(pk=part.pk, workshop=workshop)
            offer.part = locked_part
            if offer.is_preferred:
                PartSupplierOffer.objects.filter(part=locked_part).exclude(pk=offer.pk).update(is_preferred=False)
                locked_part.cost_price = offer.net_purchase_price
                locked_part.save(update_fields=("cost_price", "updated_at"))
            offer.save()
        messages.success(request, _("Supplier offer saved."))
        return redirect("part_detail", pk=part.pk)
    return render(request, "parts/part_supplier_offer_form.html", {"form": form, "part": part, "offer": instance})


@login_required
def part_document_upload(request, part_pk):
    if denied := _deny_mechanic(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    part = get_object_or_404(Part, pk=part_pk, workshop=workshop)
    form = PartDocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.part = part
        document.uploaded_by = request.user
        document.full_clean()
        document.save()
        messages.success(request, _("Attachment added to the part details."))
        return redirect("part_detail", pk=part.pk)
    return render(request, "parts/part_document_form.html", {"form": form, "part": part})


def _can_manage_purchasing(user):
    return (
        user.is_administrator
        or getattr(user, "profile", "") == "warehouse"
        or user.has_perm("parts.manage_supplier_purchasing")
    )


def _deny_purchasing_access(request):
    if not _can_manage_purchasing(request.user):
        return HttpResponseForbidden("Solo il magazziniere o un amministratore può gestire gli acquisti.")
    return None


@login_required
def purchase_order_create(request):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    order = PurchaseOrder(workshop=workshop)
    form = PurchaseOrderForm(request.POST or None, instance=order, workshop=workshop)
    line_formset = PurchaseOrderLineFormSet(
        request.POST or None,
        instance=order,
        form_kwargs={"workshop": workshop},
    )
    if request.method == "POST" and form.is_valid() and line_formset.is_valid():
        with transaction.atomic():
            order = form.save(commit=False)
            order.workshop = workshop
            order.created_by = request.user
            year = timezone.localdate().year
            count = PurchaseOrder.objects.filter(
                workshop=workshop,
                order_date__year=year,
            ).count() + 1
            order.order_number = f"OF-{year}-{count:04d}"
            order.save()
            line_formset.instance = order
            lines = line_formset.save(commit=False)
            for line in lines:
                line.quantity_received = 0
                if line.quantity_ordered is None:
                    line.quantity_ordered = line.quantity_required
                if line.unit_price is None:
                    list_item = supplier_price_for_date(
                        line.part,
                        order.supplier,
                        order.order_date,
                    )
                    offer = line.part.supplier_offers.filter(
                        supplier=order.supplier,
                    ).first()
                    if list_item:
                        line.unit_price = list_item.unit_price
                        line.discount_percent = list_item.discount_percent
                    elif offer:
                        line.unit_price = offer.net_purchase_price
                        line.discount_percent = offer.discount_percent
                line.save()
            for deleted in line_formset.deleted_objects:
                deleted.delete()
        messages.success(request, "Ordine fornitore creato.")
        return redirect("purchase_order_detail", pk=order.pk)
    return render(request, "parts/purchase_order_form.html", {
        "form": form,
        "line_formset": line_formset,
    })


@login_required
def purchase_order_list(request):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    orders = PurchaseOrder.objects.filter(
        workshop=workshop,
        status__in=("open", "partially_received"),
    ).select_related("supplier").prefetch_related("lines__part")
    return render(request, "parts/purchase_order_list.html", {"purchase_orders": orders})


@login_required
def purchase_order_detail(request, pk):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "workshop").prefetch_related("lines__part"),
        pk=pk,
        workshop=workshop,
    )
    if request.method == "POST":
        if request.POST.get("action") == "close":
            with transaction.atomic():
                locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk, workshop=workshop)
                if locked.status not in ("open", "partially_received"):
                    messages.error(request, "L'ordine non può essere saldato nello stato attuale.")
                else:
                    locked.status = "closed"
                    locked.closed_at = timezone.now()
                    locked.save(update_fields=("status", "closed_at"))
                    logger.info(
                        "Ordine fornitore saldato",
                        extra={"purchase_order_id": locked.pk, "supplier_id": locked.supplier_id, "user_id": request.user.pk},
                    )
                    messages.success(request, "Ordine fornitore saldato, anche con righe non completamente ricevute.")
            return redirect("purchase_order_detail", pk=order.pk)
        if request.POST.get("action") != "prices":
            return HttpResponseNotAllowed(["GET", "POST"])
        if order.status not in ("open", "sent", "partially_received"):
            messages.error(request, "I prezzi non possono essere modificati su un ordine chiuso o annullato.")
            return redirect("purchase_order_detail", pk=order.pk)

        updates = []
        errors = []
        for line in order.lines.all():
            try:
                price = Decimal(request.POST.get(f"price_{line.pk}", ""))
                discount = Decimal(request.POST.get(f"discount_{line.pk}", ""))
                if price < 0 or not 0 <= discount <= 100:
                    raise InvalidOperation
            except (InvalidOperation, TypeError):
                errors.append(f"{line.part.part_number}: prezzo o sconto non valido.")
            else:
                updates.append((line.pk, price, discount))
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            with transaction.atomic():
                for line_id, price, discount in updates:
                    line = PurchaseOrderLine.objects.select_for_update().get(
                        pk=line_id, purchase_order=order,
                    )
                    line.unit_price = price
                    line.discount_percent = discount
                    line.save(update_fields=("unit_price", "discount_percent"))
            logger.info(
                "Prezzi ordine fornitore aggiornati",
                extra={"purchase_order_id": order.pk, "supplier_id": order.supplier_id, "user_id": request.user.pk},
            )
            messages.success(request, "Prezzi e sconti dell'ordine aggiornati.")
        return redirect("purchase_order_detail", pk=order.pk)

    return render(request, "parts/purchase_order_detail.html", {"purchase_order": order})


@login_required
def purchase_order_receive(request, pk):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    order = get_object_or_404(
        PurchaseOrder.objects.prefetch_related("lines__part"),
        pk=pk,
        workshop=workshop,
    )
    if order.status not in ("open", "sent", "partially_received"):
        messages.error(request, "L'ordine non è disponibile per registrare altre entrate.")
        return redirect("purchase_order_detail", pk=order.pk)
    if request.method == "POST":
        receipt_number = request.POST.get("receipt_number", "").strip()
        if not receipt_number:
            messages.error(request, "Inserisci il numero della bolla di entrata.")
            return redirect("purchase_order_receive", pk=order.pk)
        if GoodsReceipt.objects.filter(
            workshop=workshop, receipt_number=receipt_number,
        ).exclude(purchase_order=order).exists():
            messages.error(request, "Il numero bolla è già associato a un altro ordine.")
            return redirect("purchase_order_receive", pk=order.pk)
        received = []
        errors = []
        for line in order.lines.all():
            raw_quantity = request.POST.get(f"received_{line.pk}", "").strip()
            if not raw_quantity:
                continue
            try:
                quantity = Decimal(raw_quantity)
                if quantity <= 0:
                    raise InvalidOperation
            except (InvalidOperation, TypeError):
                errors.append(f"{line.part.part_number}: quantità non valida.")
            else:
                received.append((line, quantity))
        if not received:
            errors.append("Inserisci almeno una quantità ricevuta.")
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("purchase_order_receive", pk=order.pk)
        try:
            with transaction.atomic():
                for line, quantity in received:
                    receive_purchase_order_line(
                        line,
                        quantity,
                        user=request.user,
                        receipt_number=receipt_number,
                    )
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)
            return redirect("purchase_order_receive", pk=order.pk)
        messages.success(request, "Entrata merce registrata.")
        return redirect("purchase_order_detail", pk=order.pk)
    for line in order.lines.all():
        line.quantity_remaining = line.quantity_ordered - line.quantity_received
    return render(request, "parts/purchase_order_receive.html", {"purchase_order": order})


@login_required
def purchase_order_document(request, pk):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier").prefetch_related("lines__part"),
        pk=pk,
        workshop=workshop,
    )
    response = HttpResponse(purchase_order_pdf(order), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="ordine-fornitore-{order.pk}.pdf"'
    return response


@login_required
def goods_receipt_document(request, pk):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    receipt = get_object_or_404(
        GoodsReceipt.objects.select_related("purchase_order", "purchase_order__supplier")
        .prefetch_related("lines__purchase_order_line__part"),
        pk=pk,
        workshop=workshop,
    )
    response = HttpResponse(goods_receipt_pdf(receipt), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="bolla-entrata-{receipt.pk}.pdf"'
    return response


@login_required
def supplier_price_list_list(request):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    price_lists = SupplierPriceList.objects.filter(workshop=workshop).select_related(
        "supplier",
    ).prefetch_related("items")
    suppliers = CamperOwner.objects.filter(
        workshop=workshop,
        kind__in=("supplier", "both"),
    )
    return render(request, "parts/supplier_price_list_list.html", {
        "price_lists": price_lists,
        "suppliers": suppliers,
    })


@login_required
def supplier_price_list_detail(request, pk):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    price_list = get_object_or_404(
        SupplierPriceList.objects.select_related("supplier"),
        pk=pk,
        workshop=workshop,
    )
    if request.method == "POST":
        valid_from = request.POST.get("valid_from", "").strip()
        valid_to = request.POST.get("valid_to", "").strip()
        try:
            price_list.valid_from = date.fromisoformat(valid_from)
            price_list.valid_to = date.fromisoformat(valid_to) if valid_to else None
        except (TypeError, ValueError):
            messages.error(request, "Inserisci date di validità valide.")
            return redirect("supplier_price_list_detail", pk=price_list.pk)
        if price_list.valid_to and price_list.valid_to < price_list.valid_from:
            messages.error(request, "La data futura non può precedere quella attuale.")
            return redirect("supplier_price_list_detail", pk=price_list.pk)
        price_list.is_active = request.POST.get("is_active") == "on"
        price_list.save(update_fields=("valid_from", "valid_to", "is_active"))
        messages.success(request, "Testata listino fornitore salvata.")
        return redirect("supplier_price_list_detail", pk=price_list.pk)
    return render(request, "parts/supplier_price_list_detail.html", {
        "price_list": price_list,
    })


@login_required
def supplier_price_list_grid(request, pk):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    price_list = get_object_or_404(SupplierPriceList, pk=pk, workshop=workshop)
    search = request.GET.get("q", "").strip()
    items = SupplierPriceListItem.objects.filter(
        price_list=price_list,
        part__isnull=False,
    ).select_related("part").order_by("part__part_number", "pk")
    if search:
        items = items.filter(
            models.Q(part__part_number__icontains=search)
            | models.Q(part__name__icontains=search)
            | models.Q(supplier_article_code__icontains=search)
            | models.Q(internal_article_code__icontains=search)
        )
    if request.method == "POST":
        changed_count = 0
        for item in items:
            current = request.POST.get(f"current_{item.pk}", "").strip().replace(",", ".")
            future = request.POST.get(f"future_{item.pk}", "").strip().replace(",", ".")
            try:
                item.unit_price = Decimal(current) if current else item.unit_price
                item.future_price = Decimal(future) if future else None
            except (InvalidOperation, TypeError):
                continue
            if item.unit_price < 0 or (item.future_price is not None and item.future_price < 0):
                continue
            item.valid_from = price_list.valid_from
            item.future_valid_from = price_list.valid_to
            item.save(update_fields=("unit_price", "valid_from", "future_price", "future_valid_from"))
            changed_count += 1
        if changed_count:
            messages.success(request, f"Aggiornate {changed_count} righe prezzo.")
        return redirect("supplier_price_list_grid", pk=price_list.pk)
    page = Paginator(items, 50).get_page(request.GET.get("page"))
    return render(request, "parts/supplier_price_list_grid.html", {
        "price_list": price_list,
        "items": page,
        "page_obj": page,
        "search": search,
    })


@login_required
def supplier_price_list_add_item(request, pk):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    price_list = get_object_or_404(SupplierPriceList, pk=pk, workshop=workshop)
    search = request.GET.get("q", "").strip()
    parts = Part.objects.filter(workshop=workshop).order_by("part_number", "name")
    if search:
        parts = parts.filter(
            models.Q(part_number__icontains=search)
            | models.Q(name__icontains=search)
            | models.Q(description__icontains=search)
        )
    page = Paginator(parts, 50).get_page(request.GET.get("page"))
    if request.method == "POST":
        try:
            part = Part.objects.get(pk=request.POST.get("part"), workshop=workshop)
        except (Part.DoesNotExist, TypeError, ValueError):
            messages.error(request, "Seleziona un articolo valido.")
            return redirect("supplier_price_list_add_item", pk=price_list.pk)
        supplier_code = request.POST.get("supplier_article_code", "").strip()
        current_raw = request.POST.get("current_price", "").strip().replace(",", ".")
        future_raw = request.POST.get("future_price", "").strip().replace(",", ".")
        if not supplier_code:
            messages.error(request, "Il codice articolo fornitore è obbligatorio.")
            return redirect("supplier_price_list_add_item", pk=price_list.pk)
        if not current_raw:
            messages.error(request, "Il prezzo corrente è obbligatorio.")
            return redirect("supplier_price_list_add_item", pk=price_list.pk)
        try:
            current_price = Decimal(current_raw)
            future_price = Decimal(future_raw) if future_raw else None
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Inserisci prezzi numerici validi.")
            return redirect("supplier_price_list_add_item", pk=price_list.pk)
        if current_price < 0 or (future_price is not None and future_price < 0):
            messages.error(request, "I prezzi non possono essere negativi.")
            return redirect("supplier_price_list_add_item", pk=price_list.pk)
        if SupplierPriceListItem.objects.filter(price_list=price_list, part=part).exists():
            messages.error(request, "Esiste già una riga prezzo per questo articolo.")
            return redirect("supplier_price_list_grid", pk=price_list.pk)
        SupplierPriceListItem.objects.create(
            price_list=price_list,
            supplier_article_code=supplier_code,
            internal_article_code=part.part_number,
            part=part,
            unit_price=current_price,
            valid_from=price_list.valid_from,
            future_price=future_price,
            future_valid_from=price_list.valid_to,
        )
        messages.success(request, "Prezzo fornitore aggiunto.")
        return redirect("supplier_price_list_grid", pk=price_list.pk)
    return render(request, "parts/supplier_price_list_add_item.html", {
        "price_list": price_list,
        "parts": page,
        "page_obj": page,
        "search": search,
    })


def _read_supplier_price_rows(upload):
    extension = os.path.splitext(upload.name)[1].lower()
    if extension == ".xlsx":
        workbook = load_workbook(upload, read_only=True, data_only=True)
        try:
            worksheet = workbook.active
            rows = worksheet.iter_rows(values_only=True)
            headers = [str(value or "").strip() for value in next(rows, ())]
            return [
                dict(zip(headers, row))
                for row in rows
                if any(value is not None for value in row)
            ], headers
        finally:
            workbook.close()
    raise ValidationError("Formato non supportato. Carica esclusivamente un file Excel .xlsx.")


def _price_row_value(row, *names):
    normalized = {
        str(key or "").strip().lower().replace(" ", "_"): value
        for key, value in row.items()
    }
    for name in names:
        if name in normalized:
            return normalized[name]
    return None


@login_required
def supplier_price_list_import(request):
    if denied := _deny_purchasing_access(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    suppliers = CamperOwner.objects.filter(workshop=workshop, kind__in=("supplier", "both"))
    errors = []
    imported_count = 0
    if request.method == "POST":
        supplier = suppliers.filter(pk=request.POST.get("supplier")).first()
        code = supplier.supplier_code if supplier else ""
        name = f"Listino {supplier}" if supplier else ""
        upload = request.FILES.get("file")
        try:
            valid_from = date.fromisoformat(request.POST.get("valid_from", ""))
        except (TypeError, ValueError):
            valid_from = None
            errors.append("Inserisci una data di inizio validità valida.")
        raw_valid_to = request.POST.get("valid_to", "")
        try:
            valid_to = date.fromisoformat(raw_valid_to) if raw_valid_to else None
        except (TypeError, ValueError):
            valid_to = None
            errors.append("Inserisci una data finale di validità valida.")
        if supplier is None:
            errors.append("Seleziona un fornitore valido.")
        if not code:
            errors.append("Inserisci il codice del listino.")
        if valid_to and valid_from and valid_to < valid_from:
            errors.append("La data finale non può precedere quella iniziale.")
        if upload is None:
            errors.append("Seleziona il file del listino.")
        if supplier and code and SupplierPriceList.objects.filter(
            workshop=workshop, supplier=supplier, code=code,
        ).exists():
            errors.append("Esiste già un listino con questo codice per il fornitore.")
        rows = []
        if upload is not None:
            try:
                rows, headers = _read_supplier_price_rows(upload)
                normalized_headers = {
                    str(value or "").strip().lower().replace(" ", "_") for value in headers
                }
                if not normalized_headers.intersection(
                    ("supplier_article_code", "codice_articolo_fornitore"),
                ):
                    errors.append("Manca la colonna codice_articolo_fornitore.")
                if not normalized_headers.intersection(("unit_price", "prezzo")):
                    errors.append("Manca la colonna prezzo.")
                if not normalized_headers.intersection(
                    ("internal_article_code", "codice_interno", "articolo"),
                ):
                    errors.append(
                        "Manca la relazione obbligatoria tra codice fornitore e articolo interno "
                        "(colonna codice_interno o articolo)."
                    )
            except (
                BadZipFile,
                InvalidFileException,
                UnicodeDecodeError,
                csv.Error,
                OSError,
                ValidationError,
            ) as error:
                errors.append(str(error))
                rows = []
        import_allowed = not errors
        valid_rows = []
        seen_codes = set()
        for row_number, row in enumerate(rows, start=2):
            supplier_code = str(_price_row_value(row, "supplier_article_code", "codice_articolo_fornitore") or "").strip()
            internal_code = str(_price_row_value(
                row,
                "internal_article_code",
                "codice_interno",
                "codice_articolo_interno",
                "articolo",
            ) or "").strip()
            try:
                price = Decimal(str(_price_row_value(row, "unit_price", "prezzo")))
                discount_value = _price_row_value(row, "discount_percent", "sconto")
                discount = Decimal(str(discount_value or "0"))
                if price < 0 or not 0 <= discount <= 100:
                    raise InvalidOperation
            except (InvalidOperation, TypeError, ValueError):
                errors.append(f"Riga {row_number}: prezzo o sconto non valido.")
                continue
            if not supplier_code:
                errors.append(f"Riga {row_number}: codice articolo fornitore mancante.")
                continue
            if supplier_code in seen_codes:
                errors.append(f"Riga {row_number}: codice fornitore duplicato {supplier_code}.")
                continue
            seen_codes.add(supplier_code)
            if not internal_code:
                errors.append(
                    f"Riga {row_number}: relazione articolo interno obbligatoria."
                )
                continue
            part = Part.objects.filter(workshop=workshop, part_number=internal_code).first()
            if part is None:
                errors.append(f"Riga {row_number}: articolo interno {internal_code} non trovato.")
                continue
            valid_rows.append((supplier_code, internal_code, part, price, discount))
        if import_allowed and supplier and code and valid_from and upload and valid_rows:
            with transaction.atomic():
                price_list = SupplierPriceList.objects.create(
                    workshop=workshop,
                    supplier=supplier,
                    code=code,
                    name=name,
                    valid_from=valid_from,
                    valid_to=valid_to,
                )
                SupplierPriceListItem.objects.bulk_create([
                    SupplierPriceListItem(
                        price_list=price_list,
                        supplier_article_code=supplier_code,
                        internal_article_code=internal_code,
                        part=part,
                        unit_price=price,
                        discount_percent=discount,
                    )
                    for supplier_code, internal_code, part, price, discount in valid_rows
                ])
            imported_count = len(valid_rows)
            messages.success(request, f"Importate {imported_count} righe nel listino {price_list.code}.")
            logger.info(
                "Listino fornitore importato",
                extra={"supplier_id": supplier.pk, "user_id": request.user.pk, "row_count": imported_count},
            )
    price_lists = SupplierPriceList.objects.filter(workshop=workshop).select_related("supplier")
    return render(request, "parts/supplier_price_list_list.html", {
        "price_lists": price_lists,
        "suppliers": suppliers,
        "errors": errors,
        "imported_count": imported_count,
    })
