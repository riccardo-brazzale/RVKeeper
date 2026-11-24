from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from fleet.models import Camper
from orders.forms import CustomerItemDiscountFormSet
from workshops.models import Membership
from .forms import ClientSupplierForm, ContactDocumentForm
from .models import CamperOwner, ContactDocument


def _active_workshop(user):
    membership = Membership.objects.filter(user=user, is_active=True, workshop__is_active=True).select_related("workshop").first()
    return membership.workshop if membership else None


def _can_manage_contacts(user):
    return getattr(user, "profile", "") == "admin" or user.is_superuser


@login_required
def customer_list(request):
    if not _can_manage_contacts(request.user):
        return HttpResponseForbidden(_("Customer records are restricted to management roles."))
    workshop = _active_workshop(request.user)
    contacts = CamperOwner.objects.filter(
        workshop=workshop,
        kind__in=("customer", "both"),
    ).annotate(camper_count=models.Count("campers", distinct=True))
    query = request.GET.get("q", "").strip()
    if query:
        contacts = contacts.filter(
            models.Q(company_name__icontains=query)
            | models.Q(first_name__icontains=query)
            | models.Q(last_name__icontains=query)
            | models.Q(phone__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(vat_number__icontains=query)
        )
    return render(request, "clientandsuppliers/customer_list.html", {
        "contacts": Paginator(contacts.order_by("last_name", "first_name", "company_name", "pk"), 50).get_page(request.GET.get("page")),
        "page_obj": Paginator(contacts.order_by("last_name", "first_name", "company_name", "pk"), 50).get_page(request.GET.get("page")),
        "has_workshop": workshop is not None,
        "query": query,
    })


@login_required
def supplier_list(request):
    if not _can_manage_contacts(request.user):
        return HttpResponseForbidden(_("Supplier records are restricted to management roles."))
    workshop = _active_workshop(request.user)
    contacts = CamperOwner.objects.filter(
        workshop=workshop,
        kind__in=("supplier", "both"),
    )
    query = request.GET.get("q", "").strip()
    if query:
        contacts = contacts.filter(
            models.Q(company_name__icontains=query)
            | models.Q(first_name__icontains=query)
            | models.Q(last_name__icontains=query)
            | models.Q(phone__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(vat_number__icontains=query)
        )
    return render(request, "clientandsuppliers/supplier_list.html", {
        "contacts": Paginator(contacts.order_by("last_name", "first_name", "company_name", "pk"), 50).get_page(request.GET.get("page")),
        "page_obj": Paginator(contacts.order_by("last_name", "first_name", "company_name", "pk"), 50).get_page(request.GET.get("page")),
        "has_workshop": workshop is not None,
        "query": query,
    })


@login_required
def contact_list(request):
    if not _can_manage_contacts(request.user):
        return HttpResponseForbidden(_("Customer and supplier records are restricted to management roles."))
    workshop = _active_workshop(request.user)
    contacts = CamperOwner.objects.filter(workshop=workshop).annotate(
        camper_count=models.Count("campers", distinct=True)
    ) if workshop else CamperOwner.objects.none()
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
        return HttpResponseForbidden(_("Customer and supplier records are restricted to management roles."))
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, _("Your account is not associated with an active workshop."))
        return redirect("customers")
    initial = {}
    if request.GET.get("kind") in ("customer", "supplier"):
        initial["kind"] = request.GET["kind"]
    form = ClientSupplierForm(
        request.POST or None,
        initial=initial,
        workshop=workshop,
    )
    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.workshop = workshop
        contact.save()
        messages.success(request, _("Contact created."))
        return redirect("customers")
    return render(request, "clientandsuppliers/contact_form.html", {"form": form, "title": _("New contact")})


@login_required
def contact_edit(request, pk):
    if not _can_manage_contacts(request.user):
        return HttpResponseForbidden(_("Customer and supplier records are restricted to management roles."))
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, _("Your account is not associated with an active workshop."))
        return redirect("customers")
    contact = get_object_or_404(CamperOwner, pk=pk, workshop=workshop)
    form = ClientSupplierForm(request.POST or None, instance=contact, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Contact updated."))
        return redirect("customers")
    return render(request, "clientandsuppliers/contact_form.html", {
        "form": form, "title": _("Edit contact"), "contact": contact,
    })


@login_required
def contact_detail(request, pk):
    if not _can_manage_contacts(request.user):
        return HttpResponseForbidden(_("Customer and supplier records are restricted to management roles."))
    workshop = _active_workshop(request.user)
    contact = get_object_or_404(CamperOwner, pk=pk, workshop=workshop)
    form = ContactDocumentForm(request.POST or None, request.FILES or None)
    discount_formset = CustomerItemDiscountFormSet(
        request.POST if request.POST.get("save_discounts") else None,
        instance=contact,
        form_kwargs={"workshop": workshop},
    )
    if request.method == "POST" and request.POST.get("save_discounts") and discount_formset.is_valid():
        for discount in discount_formset.save(commit=False):
            discount.customer = contact
            discount.full_clean()
            discount.save()
        for discount in discount_formset.deleted_objects:
            discount.delete()
        messages.success(request, _("Customer discounts updated."))
        return redirect("customer_detail", pk=contact.pk)
    if request.method == "POST" and not request.POST.get("save_discounts") and form.is_valid():
        document = form.save(commit=False)
        document.contact = contact
        document.uploaded_by = request.user
        document.full_clean()
        document.save()
        return redirect("customer_detail", pk=contact.pk)
    return render(request, "clientandsuppliers/contact_detail.html", {
        "contact": contact, "form": form, "discount_formset": discount_formset,
        "documents": contact.documents.select_related("category", "uploaded_by"),
        "campers": Camper.objects.filter(workshop=workshop, owner=contact).order_by("internal_number"),
    })
