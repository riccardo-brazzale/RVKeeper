from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from clientandsuppliers.models import CamperOwner
from .forms import CamperForm, CamperPhotoForm
from .models import Camper, CamperPhoto

from orders.views import (
    CUSTOMER_APPROVAL_THRESHOLD,
    FORM_EXCLUDES,
    MODULES,
    _active_workshop,
    _audit,
    _can_approve_parts,
    _can_manage_parts,
    _create_warehouse_note,
    _forbidden_for_mechanic,
    _is_mechanic,
    _job_minutes,
    _module,
    _next_job_number,
    _notify_new_parts_requests,
    _notify_profile,
    _notify_requester,
    _parts_request_quote,
    _render_my_jobs,
    _set_initial_parts_request_status,
    _workshop_or_redirect,
    audit_log,
    dashboard,
    data_export,
    job_action,
    job_complete,
    job_parts_request,
    mark_notifications_read,
    mechanic_open_job,
    my_jobs,
    notifications,
    notifications_feed,
    parts_request_action,
    report,
    work_order_billing,
    work_order_detail,
    work_order_report,
    workflow_create,
    workflow_edit,
    workflow_list,
    workflow_status_action,
)


def camper_list(request):
    if denied := _forbidden_for_mechanic(request): return denied
    workshop = _active_workshop(request.user)
    campers = Camper.objects.filter(workshop=workshop, is_active=True).annotate(
        photo_count=Count("photos", distinct=True)
    ) if workshop else Camper.objects.none()
    search = request.GET.get("q", "").strip()
    if search:
        campers = campers.filter(models.Q(plate__icontains=search) | models.Q(vin__icontains=search) |
            models.Q(internal_number__icontains=search) | models.Q(brand__icontains=search) |
            models.Q(model__icontains=search) | models.Q(owner__company_name__icontains=search) |
            models.Q(owner__first_name__icontains=search) | models.Q(owner__last_name__icontains=search))
    return render(request, "fleet/camper_list.html", {"campers": campers, "has_workshop": workshop is not None, "search": search})


@login_required
def camper_create(request):
    if denied := _forbidden_for_mechanic(request): return denied
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, _("Your account is not associated with an active workshop."))
        return redirect("fleet:camper_list")

    initial = {}
    owner_id = request.GET.get("owner")
    if request.method == "GET" and owner_id:
        initial["owner"] = get_object_or_404(
            CamperOwner.objects.filter(workshop=workshop, kind__in=("customer", "both")),
            pk=owner_id,
        )
    form = CamperForm(request.POST or None, workshop=workshop, initial=initial)
    if request.method == "POST" and form.is_valid():
        camper = form.save(commit=False)
        camper.workshop = workshop
        camper.save()
        messages.success(request, _("Camper added to the fleet."))
        return redirect("fleet:camper_list")
    return render(request, "fleet/camper_form.html", {"form": form})


@login_required
def camper_edit(request, pk):
    if denied := _forbidden_for_mechanic(request): return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    camper = get_object_or_404(Camper, pk=pk, workshop=workshop)
    form = CamperForm(request.POST or None, instance=camper, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Vehicle details updated."))
        return redirect("fleet:camper_detail", pk=camper.pk)
    return render(request, "fleet/camper_form.html", {"form": form, "camper": camper})


@login_required
def camper_detail(request, pk):
    if denied := _forbidden_for_mechanic(request): return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    camper = get_object_or_404(Camper.objects.select_related("owner"), pk=pk, workshop=workshop)
    orders = camper.work_orders.order_by("-created_at").prefetch_related("jobs")
    return render(request, "fleet/camper_detail.html", {"camper": camper, "orders": orders, "photos": camper.photos.select_related("category")})




@login_required
def camper_photo_upload(request, pk):
    if denied := _forbidden_for_mechanic(request): return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    camper = get_object_or_404(Camper, pk=pk, workshop=workshop)
    form = CamperPhotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        photo = form.save(commit=False)
        photo.camper = camper
        photo.save()
        _audit(workshop, request.user, "photo_upload", Camper, camper)
        messages.success(request, _("Photo saved to the vehicle record."))
        return redirect("fleet:camper_detail", pk=camper.pk)
    return render(request, "fleet/camper_photo_form.html", {"camper": camper, "form": form})


@login_required
def camper_photo_delete(request, pk, photo_pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if denied := _forbidden_for_mechanic(request): return denied
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    camper = get_object_or_404(Camper, pk=pk, workshop=workshop)
    photo = get_object_or_404(CamperPhoto, pk=photo_pk, camper=camper)
    _audit(workshop, request.user, "photo_delete", Camper, camper, details=f"Removed photo {photo.caption or photo.image.name}")
    photo.image.delete(save=False)
    photo.delete()
    success_message = {
        "it": "Foto rimossa dall'anagrafica del veicolo.",
        "es": "Foto eliminada de la ficha del vehículo.",
    }.get(request.LANGUAGE_CODE[:2], str(_("Photo removed from the vehicle record.")))
    messages.success(request, success_message)
    return redirect("fleet:camper_detail", pk=camper.pk)
