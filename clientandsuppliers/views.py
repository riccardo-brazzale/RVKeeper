from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from workshops.models import Membership
from .forms import ClientSupplierForm
from .models import CamperOwner


def _active_workshop(user):
    membership = Membership.objects.filter(user=user, is_active=True, workshop__is_active=True).select_related("workshop").first()
    return membership.workshop if membership else None


def _can_manage_contacts(user):
    return getattr(user, "department", "") != "technician"


@login_required
def contact_list(request):
    if not _can_manage_contacts(request.user):
        return HttpResponseForbidden("L'anagrafica clienti e fornitori è riservata ai ruoli gestionali.")
    workshop = _active_workshop(request.user)
    contacts = CamperOwner.objects.filter(workshop=workshop) if workshop else CamperOwner.objects.none()
    kind = request.GET.get("tipo", "")
    if kind in ("customer", "supplier", "both"):
        contacts = contacts.filter(kind=kind)
    query = request.GET.get("q", "").strip()
    if query:
        contacts = contacts.filter(models.Q(company_name__icontains=query) | models.Q(first_name__icontains=query) |
                                   models.Q(last_name__icontains=query) | models.Q(phone__icontains=query) |
                                   models.Q(email__icontains=query) | models.Q(vat_number__icontains=query))
    return render(request, "clientandsuppliers/contact_list.html", {
        "contacts": contacts, "has_workshop": workshop is not None, "kind": kind, "query": query,
    })


@login_required
def contact_create(request):
    if not _can_manage_contacts(request.user):
        return HttpResponseForbidden("L'anagrafica clienti e fornitori è riservata ai ruoli gestionali.")
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, "Il tuo account non è associato a un'officina attiva.")
        return redirect("customers")
    form = ClientSupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.workshop = workshop
        contact.save()
        messages.success(request, "Anagrafica creata.")
        return redirect("customers")
    return render(request, "clientandsuppliers/contact_form.html", {"form": form, "title": "Nuova anagrafica"})


@login_required
def contact_edit(request, pk):
    if not _can_manage_contacts(request.user):
        return HttpResponseForbidden("L'anagrafica clienti e fornitori è riservata ai ruoli gestionali.")
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, "Il tuo account non è associato a un'officina attiva.")
        return redirect("customers")
    contact = get_object_or_404(CamperOwner, pk=pk, workshop=workshop)
    form = ClientSupplierForm(request.POST or None, instance=contact)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Anagrafica aggiornata.")
        return redirect("customers")
    return render(request, "clientandsuppliers/contact_form.html", {
        "form": form, "title": "Modifica anagrafica", "contact": contact,
    })
