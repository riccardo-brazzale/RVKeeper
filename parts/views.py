from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from workshops.models import Membership
from fleet.models import AuditLog, Notification, Part, PartDocument, PartMovement, PartSupplierOffer, WorkOrder
from .forms import PartDocumentForm, PartForm, PartSupplierOfferForm


def _active_workshop(user):
    membership = Membership.objects.filter(user=user, is_active=True, workshop__is_active=True).select_related("workshop").first()
    return membership.workshop if membership else None


def _workshop_or_redirect(request):
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, "Il tuo account non è associato a un'officina attiva.")
    return workshop


def _is_mechanic(user):
    return getattr(user, "department", "") == "technician"


def _deny_mechanic(request):
    if _is_mechanic(request.user):
        return HttpResponseForbidden("Il catalogo e gli acquisti ricambi sono gestiti dal responsabile.")
    return None


def _audit(workshop, user, action, part, details=""):
    AuditLog.objects.create(workshop=workshop, actor=user, action=action, entity_type=Part.__name__,
                            entity_id=str(part.pk), details=details or str(part))


@login_required
def inventory(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    parts = Part.objects.filter(workshop=workshop)
    query = request.GET.get("q", "").strip()
    if query:
        parts = parts.filter(models.Q(part_number__icontains=query) | models.Q(name__icontains=query) |
                             models.Q(description__icontains=query) | models.Q(location__icontains=query))
    low_stock = parts.filter(quantity__lte=models.F("min_stock"))
    for part in low_stock:
        Notification.objects.get_or_create(
            workshop=workshop, user=None, title="Scorta ricambi bassa", link="/magazzino/", read=False,
            defaults={"body": f"{part.part_number} · {part.name}: disponibili {part.quantity}, minimo {part.min_stock}"},
        )
    return render(request, "parts/part_list.html", {
        "parts": parts, "query": query, "low_stock_count": low_stock.count(), "is_mechanic": _is_mechanic(request.user),
    })


@login_required
def part_create(request):
    if denied := _deny_mechanic(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    form = PartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        part = form.save(commit=False)
        part.workshop = workshop
        part.save()
        _audit(workshop, request.user, "create", part)
        messages.success(request, "Articolo creato. Registra un movimento per caricare la giacenza iniziale.")
        return redirect("part_detail", pk=part.pk)
    return render(request, "parts/part_form.html", {"form": form, "title": "Nuovo articolo"})


@login_required
def part_edit(request, pk):
    if denied := _deny_mechanic(request):
        return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    part = get_object_or_404(Part, pk=pk, workshop=workshop)
    form = PartForm(request.POST or None, instance=part)
    if request.method == "POST" and form.is_valid():
        part = form.save()
        _audit(workshop, request.user, "update", part)
        messages.success(request, "Scheda articolo aggiornata.")
        return redirect("part_detail", pk=part.pk)
    return render(request, "parts/part_form.html", {"form": form, "title": "Modifica articolo", "part": part})


@login_required
def part_detail(request, pk):
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    part = get_object_or_404(Part, pk=pk, workshop=workshop)
    is_mechanic = _is_mechanic(request.user)
    return render(request, "parts/part_detail.html", {
        "part": part,
        "offers": [] if is_mechanic else part.supplier_offers.select_related("supplier"),
        "documents": part.documents.select_related("uploaded_by"),
        "is_mechanic": is_mechanic,
    })


@login_required
def part_movement(request, pk):
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
            messages.error(request, "Inserisci una quantità valida e un tipo di movimento.")
            return redirect("part_movement", pk=part.pk)
        with transaction.atomic():
            locked = Part.objects.select_for_update().get(pk=part.pk, workshop=workshop)
            delta = qty if kind == "in" else -qty
            if kind == "adjustment":
                delta = qty - locked.quantity
            if locked.quantity + delta < 0:
                messages.error(request, "La giacenza non può diventare negativa.")
                return redirect("part_movement", pk=part.pk)
            order_id = request.POST.get("work_order") or None
            order = get_object_or_404(orders, pk=order_id) if order_id else None
            locked.quantity += delta
            locked.save(update_fields=("quantity", "updated_at"))
            PartMovement.objects.create(workshop=workshop, part=locked, work_order=order,
                movement_type=kind, quantity=delta if kind == "adjustment" else qty,
                unit_cost=locked.cost_price, note=request.POST.get("note", "").strip(), created_by=request.user)
            _audit(workshop, request.user, "stock_" + kind, locked, f"Variazione {delta} {locked.unit}")
        messages.success(request, "Movimento di magazzino registrato.")
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
        messages.success(request, "Condizione fornitore salvata.")
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
        messages.success(request, "Allegato aggiunto alla scheda ricambio.")
        return redirect("part_detail", pk=part.pk)
    return render(request, "parts/part_document_form.html", {"form": form, "part": part})
