from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from clientandsuppliers.models import CamperOwner
from fleet.models import AuditLog, Job, PartsRequest, WorkOrder
from workshops.models import Membership, Workshop
from .forms import QuoteForm, QuoteLineFormSet
from .models import Quote


def _workshop(user):
    membership = Membership.objects.filter(user=user, is_active=True, workshop__is_active=True).select_related("workshop").first()
    return membership.workshop if membership else None


def _denied(user):
    return getattr(user, "department", "") == "technician"


def _quote_number(workshop):
    year = timezone.localdate().year
    sequence = Quote.objects.filter(workshop=workshop).count() + 1
    number = f"PREV-{year}-{sequence:04d}"
    while Quote.objects.filter(workshop=workshop, quote_number=number).exists():
        sequence += 1
        number = f"PREV-{year}-{sequence:04d}"
    return number


@login_required
def quote_list(request):
    if _denied(request.user):
        return HttpResponseForbidden("I preventivi sono riservati ai ruoli gestionali.")
    workshop = _workshop(request.user)
    quotes = Quote.objects.filter(workshop=workshop).select_related("customer", "vehicle", "work_order") if workshop else Quote.objects.none()
    return render(request, "quotes/quote_list.html", {"quotes": quotes, "has_workshop": workshop is not None})


@login_required
def quote_create(request):
    if _denied(request.user):
        return HttpResponseForbidden("I preventivi sono riservati ai ruoli gestionali.")
    workshop = _workshop(request.user)
    if workshop is None:
        messages.error(request, "Il tuo account non è associato a un'officina attiva.")
        return redirect("quotes")
    form = QuoteForm(request.POST or None, workshop=workshop)
    quote = form.save(commit=False) if request.method == "POST" and form.is_valid() else Quote(workshop=workshop)
    quote.workshop = workshop
    line_formset = QuoteLineFormSet(request.POST or None, instance=quote, form_kwargs={"workshop": workshop})
    if request.method == "POST" and form.is_valid() and line_formset.is_valid():
        with transaction.atomic():
            quote.workshop = Workshop.objects.select_for_update().get(pk=workshop.pk)
            quote.quote_number = _quote_number(quote.workshop)
            quote.created_by = request.user
            quote.full_clean()
            quote.save()
            for line in line_formset.save(commit=False):
                if line.part_id:
                    line.description = line.description or line.part.name
                    if line.unit_price == 0:
                        line.unit_price = line.part.sale_price
                    if line.standard_minutes == 0:
                        line.standard_minutes = line.part.standard_minutes
                    line.unit = line.part.unit
                line.quote = quote
                line.save()
            messages.success(request, f"Preventivo {quote.quote_number} creato.")
        return redirect("quote_detail", pk=quote.pk)
    return render(request, "quotes/quote_form.html", {"form": form, "line_formset": line_formset, "title": "Nuovo preventivo"})


@login_required
def quote_edit(request, pk):
    if _denied(request.user):
        return HttpResponseForbidden("I preventivi sono riservati ai ruoli gestionali.")
    workshop = _workshop(request.user)
    if workshop is None:
        return redirect("home")
    quote = get_object_or_404(Quote, pk=pk, workshop=workshop, status="draft", work_order__isnull=True)
    form = QuoteForm(request.POST or None, instance=quote, workshop=workshop)
    quote_form_valid = request.method != "POST" or form.is_valid()
    quote_instance = form.save(commit=False) if request.method == "POST" and quote_form_valid else quote
    quote_instance.workshop = workshop
    line_formset = QuoteLineFormSet(request.POST or None, instance=quote_instance, form_kwargs={"workshop": workshop})
    if request.method == "POST" and quote_form_valid and line_formset.is_valid():
        quote_instance.full_clean()
        quote_instance.save()
        for line in line_formset.save(commit=False):
            if line.part_id:
                line.description = line.description or line.part.name
                if line.unit_price == 0:
                    line.unit_price = line.part.sale_price
                if line.standard_minutes == 0:
                    line.standard_minutes = line.part.standard_minutes
                line.unit = line.part.unit
            line.quote = quote_instance
            line.save()
        for line in line_formset.deleted_objects:
            line.delete()
        messages.success(request, "Preventivo aggiornato.")
        return redirect("quote_detail", pk=quote.pk)
    return render(request, "quotes/quote_form.html", {"form": form, "line_formset": line_formset, "title": f"Modifica {quote.quote_number}", "quote": quote})


@login_required
def quote_detail(request, pk):
    if _denied(request.user):
        return HttpResponseForbidden("I preventivi sono riservati ai ruoli gestionali.")
    workshop = _workshop(request.user)
    if workshop is None:
        return redirect("home")
    quote = get_object_or_404(Quote.objects.select_related("customer", "vehicle", "work_order"), pk=pk, workshop=workshop)
    return render(request, "quotes/quote_detail.html", {
        "quote": quote,
        "lines": quote.lines.select_related("part"),
        "status_choices": Quote.STATUS_CHOICES,
    })


@login_required
def quote_status(request, pk):
    if _denied(request.user):
        return HttpResponseForbidden("I preventivi sono riservati ai ruoli gestionali.")
    workshop = _workshop(request.user)
    if workshop is None:
        return redirect("home")
    quote = get_object_or_404(Quote, pk=pk, workshop=workshop, work_order__isnull=True)
    allowed = {value for value, _ in Quote.STATUS_CHOICES}
    new_status = request.POST.get("status") if request.method == "POST" else None
    if new_status not in allowed:
        messages.error(request, "Stato preventivo non valido.")
    elif new_status == "approved" and quote.status not in ("draft", "sent"):
        messages.error(request, "È possibile accettare solo un preventivo in bozza o già inviato.")
    else:
        quote.status = new_status
        quote.save(update_fields=("status", "updated_at"))
        AuditLog.objects.create(workshop=workshop, actor=request.user, action="status", entity_type="Quote",
                                entity_id=str(quote.pk), details=new_status)
        messages.success(request, "Stato del preventivo aggiornato.")
    return redirect("quote_detail", pk=quote.pk)


@login_required
def quote_to_order(request, pk):
    if _denied(request.user):
        return HttpResponseForbidden("La conversione in OdL è riservata ai ruoli gestionali.")
    workshop = _workshop(request.user)
    if workshop is None:
        return redirect("home")
    if request.method != "POST":
        return redirect("quote_detail", pk=pk)
    with transaction.atomic():
        Workshop.objects.select_for_update().get(pk=workshop.pk)
        quote = get_object_or_404(Quote.objects.select_for_update().select_related("customer", "vehicle"), pk=pk, workshop=workshop)
        if quote.status != "approved" or quote.work_order_id:
            messages.error(request, "Solo un preventivo accettato e non ancora convertito può generare un OdL.")
            return redirect("quote_detail", pk=quote.pk)
        sequence = WorkOrder.objects.filter(workshop=workshop).count() + 1
        ro_number = f"RO-{timezone.localdate().year}-{sequence:04d}"
        while WorkOrder.objects.filter(workshop=workshop, ro_number=ro_number).exists():
            sequence += 1
            ro_number = f"RO-{timezone.localdate().year}-{sequence:04d}"
        vehicle = quote.vehicle
        order = WorkOrder.objects.create(
            workshop=workshop, customer=quote.customer, vehicle=vehicle, ro_number=ro_number,
            make=vehicle.brand if vehicle else "", model=vehicle.model if vehicle else "",
            customer_name=str(quote.customer), customer_phone=quote.customer.phone,
            customer_email=quote.customer.email, odometer=vehicle.mileage if vehicle else None,
            reception_notes=quote.description, created_by=request.user,
        )
        job_number = 0
        for line in quote.lines.select_related("part"):
            if line.line_type == "part":
                PartsRequest.objects.create(
                    workshop=workshop, work_order=order, part=line.part,
                    custom_item="" if line.part_id else line.description,
                    unit=line.unit, quantity_requested=line.quantity,
                    notes=f"Da preventivo {quote.quote_number}", requested_by=request.user,
                )
            else:
                job_number += 1
                Job.objects.create(
                    workshop=workshop, work_order=order, job_number=job_number,
                    title=line.description[:200], description=f"Preventivo {quote.quote_number}",
                    category="customer_pay", standard_minutes=line.standard_minutes,
                )
        quote.work_order = order
        quote.save(update_fields=("work_order", "updated_at"))
        AuditLog.objects.create(workshop=workshop, actor=request.user, action="create_from_quote",
            entity_type="WorkOrder", entity_id=str(order.pk), work_order=order,
            details=f"Creato da preventivo {quote.quote_number}")
    messages.success(request, f"Preventivo convertito nell'ordine di lavoro {order.ro_number}.")
    return redirect("orders")
