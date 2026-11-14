from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Count, Sum
from django.forms import modelform_factory
from django.core import serializers
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from io import BytesIO
from xml.sax.saxutils import escape

from workshops.models import Membership
from workshops.models import Role, Workshop
from .forms import CamperForm, CamperPhotoForm, WorkOrderForm
from .models import (Attachment, AuditLog, Camper, CamperPhoto, DocumentCategory, JobAssignment,
                     JobNote, JobParticipation, Notification, PartsRequest, TimeEvent, WarrantyClaim,
                     WarrantyReturn)
from clientandsuppliers.models import CamperOwner
from orders.models import Job, JobCall, PauseReason, WorkOrder
from parts.models import Part, PartDocument, PartMovement, PartSupplierOffer
from quotes.models import Quote, QuoteLine
from parts.views import part_detail, part_document_upload, part_movement, part_supplier_offer


def _active_workshop(user):
    membership = Membership.objects.filter(
        user=user, is_active=True, workshop__is_active=True
    ).select_related("workshop").first()
    return membership.workshop if membership else None


def _is_mechanic(user):
    return getattr(user, "department", "") == "technician"


def _forbidden_for_mechanic(request):
    if _is_mechanic(request.user):
        return HttpResponseForbidden(_("Your profile can only access work orders and parts."))
    return None


@login_required
def camper_list(request):
    if denied := _forbidden_for_mechanic(request): return denied
    workshop = _active_workshop(request.user)
    campers = Camper.objects.filter(workshop=workshop, is_active=True) if workshop else Camper.objects.none()
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


MODULES = {
    "orders": (WorkOrder, _("Work orders"), ("ro_number", "vehicle", "customer", "customer_phone", "status", "completed_at", "invoiced")),
    "jobs": (Job, _("Jobs and technicians"), ("work_order", "title", "department", "status")),
    "requests": (PartsRequest, _("Parts requests"), ("work_order", "part", "supplier_offer", "custom_item", "quantity_requested", "status")),
    "claims": (WarrantyClaim, _("Warranty claims"), ("work_order", "component", "problem_description", "status")),
    "returns": (WarrantyReturn, _("Warranty returns"), ("work_order", "part_name", "quantity", "status")),
    "attachments": (Attachment, _("Attachments"), ("work_order", "category", "file_name", "caption", "uploaded_by", "created_at")),
    "notes": (JobNote, _("Job notes"), ("job", "author", "language", "text", "created_at")),
    "assignments": (JobAssignment, _("Technician assignments"), ("job", "from_technician", "to_technician", "reason", "created_at")),
}
FORM_EXCLUDES = {
    WorkOrder: ("workshop", "status", "created_by", "completed_at", "invoiced", "invoiced_at", "invoiced_by", "created_at", "updated_at"),
    Job: ("workshop", "status", "started_at", "completed_at", "created_at", "updated_at"),
    PartsRequest: ("workshop", "requested_by", "quantity_delivered", "purchase_price", "delivered_at", "delivered_by", "inventory_applied", "created_at", "updated_at"),
    WarrantyClaim: ("workshop", "requested_by", "decided_by", "decided_at", "created_at", "updated_at"),
    WarrantyReturn: ("workshop", "requested_by", "decided_by", "decided_at", "created_at"),
    Attachment: ("workshop", "file_name", "uploaded_by", "created_at"),
    JobNote: ("workshop", "author", "created_at"),
    JobAssignment: ("workshop", "created_at"),
}


def _module(module):
    try:
        return MODULES[module]
    except KeyError as error:
        raise Http404 from error


def _workshop_or_redirect(request):
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, _("Your account is not associated with an active workshop."))
    return workshop


def _audit(workshop, user, action, model, obj, details=""):
    related_order = obj if isinstance(obj, WorkOrder) else getattr(obj, "work_order", None)
    if related_order is None and hasattr(obj, "job_id") and obj.job_id:
        related_order = Job.objects.filter(pk=obj.job_id).select_related("work_order").first()
        related_order = related_order.work_order if related_order else None
    AuditLog.objects.create(workshop=workshop, actor=user, action=action,
                            entity_type=model.__name__, entity_id=str(obj.pk),
                            work_order=related_order,
                            details=details or str(obj))


def _job_minutes(job):
    running = {}
    seconds = 0
    for event in job.time_events.order_by("event_at", "pk"):
        key = event.mechanic_id
        if event.event_type in ("start", "resume"):
            running[key] = event.event_at
        elif event.event_type in ("pause", "finish", "waiting") and key in running:
            seconds += max(0, (event.event_at - running.pop(key)).total_seconds())
    now = timezone.now()
    seconds += sum(max(0, (now - started).total_seconds()) for started in running.values())
    return int(seconds // 60)


@login_required
def dashboard(request):
    if _is_mechanic(request.user):
        return redirect("jobs")
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return render(request, "fleet/dashboard.html", {"has_workshop": False})
    orders = WorkOrder.objects.filter(workshop=workshop)
    jobs = Job.objects.filter(workshop=workshop)
    low_stock = Part.objects.filter(workshop=workshop, quantity__lte=models.F("min_stock"))
    context = {
        "has_workshop": True,
        "orders_open": orders.exclude(status__in=("completed", "cancelled")).count(),
        "jobs_active": jobs.filter(status="in_progress").count(),
        "requests_open": PartsRequest.objects.filter(workshop=workshop).exclude(status__in=("delivered", "cancelled")).count(),
        "low_stock_count": low_stock.count(),
        "recent_orders": orders[:8],
        "active_jobs": jobs.filter(status__in=("in_progress", "paused", "waiting_parts", "waiting_warranty"))[:8],
    }
    return render(request, "fleet/dashboard.html", context)


@login_required
def workflow_list(request, module):
    if module == "owners":
        return redirect("customers")
    if module == "parts":
        return redirect("inventory")
    if module not in ("orders", "jobs", "parts", "requests") and _forbidden_for_mechanic(request):
        return _forbidden_for_mechanic(request)
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    model, title, columns = _module(module)
    if module == "requests" and _is_mechanic(request.user):
        columns = tuple(column for column in columns if column != "supplier_offer")
    if module == "orders" and _is_mechanic(request.user):
        columns = tuple(column for column in columns if column != "invoiced")
    objects = model.objects.filter(workshop=workshop).select_related(*[f for f in columns if f in {x.name for x in model._meta.fields} and model._meta.get_field(f).is_relation])
    if model is PartsRequest:
        objects = objects.select_related("work_order", "part", "supplier_offer__supplier")
    if model is WarrantyClaim or model is WarrantyReturn:
        objects = objects.select_related("work_order")
    if model is Job:
        objects = objects.select_related("work_order").prefetch_related("participations__mechanic")
    if model is Attachment:
        objects = objects.select_related("work_order", "uploaded_by")
    display_rows = []
    for obj in objects:
        values = []
        for name in columns:
            if name == "custom_item" and getattr(obj, "part_id", None):
                value = ""
            else:
                field = model._meta.get_field(name)
                if module == "orders" and name == "customer":
                    value = str(obj.customer) if obj.customer_id else obj.customer_name
                elif module == "orders" and name == "customer_phone":
                    value = obj.customer.phone if obj.customer_id else obj.customer_phone
                elif field.is_relation:
                    value = str(getattr(obj, name) or "—")
                elif field.choices:
                    value = getattr(obj, f"get_{name}_display")()
                elif module == "orders" and name == "invoiced":
                    value = _("Invoiced") if obj.invoiced else _("Not invoiced")
                elif module == "orders" and name == "completed_at":
                    value = timezone.localtime(obj.completed_at).strftime("%d/%m/%Y %H:%M") if obj.completed_at else "—"
                else:
                    value = getattr(obj, name)
                if isinstance(obj, JobNote) and name == "text":
                    value = obj.translations.get(request.user.preferred_language) or value
            values.append(value)
        display_rows.append((obj, values))
    headers = {
        "orders": (_("Work order"), _("Camper"), _("Customer"), _("Customer phone"), _("Status"), _("Closed at"), _("Invoicing")),
        "jobs": (_("Work order"), _("Job"), _("Technician"), _("Status")),
        "requests": (_("Work order"), _("Part"), _("Supplier / price"), _("Custom item"), _("Requested quantity"), _("Status")),
        "claims": (_("Work order"), _("Component"), _("Problem description"), _("Status")),
        "returns": (_("Work order"), _("Part"), _("Quantity"), _("Status")),
        "attachments": (_("Work order"), _("Category"), _("File name"), _("Description"), _("Uploaded by"), _("Date")),
        "notes": (_("Job"), _("Author"), _("Language"), _("Note"), _("Date")),
        "assignments": (_("Job"), _("From"), _("To"), _("Reason"), _("Date")),
    }
    column_headers = headers.get(module, columns)
    if module == "requests" and _is_mechanic(request.user):
        column_headers = (_("Work order"), _("Part"), _("Custom item"), _("Requested quantity"), _("Status"))
    if module == "orders" and _is_mechanic(request.user):
        column_headers = (_("Work order number"), _("Camper"), _("Customer"), _("Phone"), _("Status"), _("Closed at"))
    context = {"module": module, "title": title, "objects": objects, "columns": columns, "headers": column_headers, "display_rows": display_rows, "model": model,
               "status_choices": model._meta.get_field("status").choices if any(f.name == "status" for f in model._meta.fields) else ()}
    if module == "jobs":
        context["mechanics"] = request.user.__class__.objects.filter(memberships__workshop=workshop,
            memberships__is_active=True, department="technician", is_active=True).distinct()
        context["pause_reasons"] = PauseReason.objects.filter(is_active=True)
        context["active_job_ids"] = list(JobParticipation.objects.filter(workshop=workshop, mechanic=request.user,
            is_active=True, paused_at__isnull=True).values_list("job_id", flat=True))
        context["paused_job_ids"] = list(JobParticipation.objects.filter(workshop=workshop, mechanic=request.user,
            is_active=True, paused_at__isnull=False).values_list("job_id", flat=True))
    return render(request, "fleet/workflow_list.html", context)


@login_required
def workflow_create(request, module):
    if _is_mechanic(request.user) and module in ("orders", "jobs", "parts"):
        return HttpResponseForbidden(_("You can record inventory movements; the parts catalog is managed by a supervisor."))
    if module not in ("orders", "jobs", "parts", "requests") and _forbidden_for_mechanic(request):
        return _forbidden_for_mechanic(request)
    if module == "owners":
        return redirect("customer_create")
    if module == "parts":
        return redirect("part_create")
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    model, title = _module(module)[:2]
    exclude = FORM_EXCLUDES[model]
    if model is PartsRequest and _is_mechanic(request.user):
        exclude = exclude + ("supplier", "supplier_offer")
    if model is WorkOrder:
        initial = {}
        vehicle_id = request.GET.get("vehicle")
        if request.method == "GET" and vehicle_id:
            initial["vehicle"] = get_object_or_404(
                Camper.objects.filter(
                    workshop=workshop,
                    owner__kind__in=("customer", "both"),
                ),
                pk=vehicle_id,
            )
        form = WorkOrderForm(request.POST or None, workshop=workshop, initial=initial)
    else:
        Form = modelform_factory(model, exclude=exclude)
        form = Form(request.POST or None, request.FILES or None)
    for field in form.fields.values():
        if hasattr(field, "queryset"):
            related_model = field.queryset.model
            if hasattr(related_model, "workshop"):
                field.queryset = field.queryset.filter(workshop=workshop)
                if _is_mechanic(request.user) and model is PartsRequest and related_model is WorkOrder:
                    field.queryset = field.queryset.filter(jobs__participations__mechanic=request.user, jobs__participations__is_active=True).distinct()
                if _is_mechanic(request.user) and model is PartsRequest and related_model is Job:
                    field.queryset = field.queryset.filter(participations__mechanic=request.user, participations__is_active=True)
            elif related_model._meta.label == "accounts.User":
                field.queryset = related_model.objects.filter(memberships__workshop=workshop, memberships__is_active=True, is_active=True).distinct()
            elif related_model is DocumentCategory:
                field.queryset = DocumentCategory.objects.filter(is_active=True)
            elif model is PartsRequest and related_model is PartSupplierOffer:
                field.queryset = related_model.objects.filter(part__workshop=workshop).select_related("part", "supplier")
    if model is Attachment and "file" in form.fields:
        form.fields["file"].required = True
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        for related in (getattr(obj, "work_order", None), getattr(obj, "job", None), getattr(obj, "part", None), getattr(obj, "vehicle", None), getattr(obj, "customer", None)):
            if related is not None and getattr(related, "workshop_id", workshop.pk) != workshop.pk:
                form.add_error(None, "Seleziona un elemento appartenente alla stessa officina.")
                return render(request, "fleet/workflow_form.html", {"form": form, "title": title, "module": module})
        obj.workshop = workshop
        if isinstance(obj, WorkOrder): obj.created_by = request.user
        if isinstance(obj, PartsRequest): obj.requested_by = request.user
        if isinstance(obj, PartsRequest) and obj.supplier_offer_id:
            obj.supplier = str(obj.supplier_offer.supplier)
            obj.purchase_price = obj.supplier_offer.net_purchase_price
        if isinstance(obj, WarrantyClaim): obj.requested_by = request.user
        if isinstance(obj, WarrantyReturn): obj.requested_by = request.user
        if isinstance(obj, JobNote):
            obj.author = request.user
            obj.language = request.user.preferred_language
            obj.translations = {}
            try:
                from deep_translator import GoogleTranslator
                for language, _language_label in request.user.LANGUAGE_CHOICES:
                    if language != obj.language:
                        try:
                            obj.translations[language] = GoogleTranslator(source=obj.language[:2], target=language[:2]).translate(obj.text) or ""
                        except Exception:
                            continue
            except ImportError:
                pass
        if isinstance(obj, JobAssignment) and obj.to_technician_id:
            obj.from_technician = JobParticipation.objects.filter(job_id=obj.job_id, is_active=True).values_list("mechanic_id", flat=True).first()
        if isinstance(obj, Attachment):
            obj.uploaded_by = request.user
            obj.file_name = obj.file.name
            obj.full_clean()
            obj.full_clean()
            obj.full_clean()
        obj.save()
        form.save_m2m()
        if isinstance(obj, JobAssignment) and obj.to_technician_id:
            JobCall.objects.create(workshop=workshop, job=obj.job, mechanic=obj.to_technician, called_by=request.user)
            Notification.objects.create(workshop=workshop, user=obj.to_technician, title="Chiamata su lavorazione",
                body=f"{obj.job.work_order.ro_number} · {obj.job.title}", link="/lavori/miei/", work_order=obj.job.work_order)
        _audit(workshop, request.user, "create", model, obj)
        messages.success(request, _("%(title)s: item created.") % {"title": title})
        return redirect("fleet:workflow_list", module=module)
    return render(request, "fleet/workflow_form.html", {"form": form, "title": title, "module": module})


@login_required
def workflow_edit(request, module, pk):
    if _is_mechanic(request.user) and module in ("orders", "jobs", "requests", "parts"):
        return HttpResponseForbidden(_("Only a supervisor can edit the catalog; record an inventory movement to update stock."))
    if module not in ("orders", "jobs", "parts", "requests") and _forbidden_for_mechanic(request):
        return _forbidden_for_mechanic(request)
    if module == "owners":
        return redirect("customer_edit", pk=pk)
    if module == "parts":
        return redirect("part_edit", pk=pk)
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    model, title = _module(module)[:2]
    obj = get_object_or_404(model, pk=pk, workshop=workshop)
    if model is WorkOrder:
        form = WorkOrderForm(request.POST or None, instance=obj, workshop=workshop)
    else:
        Form = modelform_factory(model, exclude=FORM_EXCLUDES[model])
        form = Form(request.POST or None, request.FILES or None, instance=obj)
    for field in form.fields.values():
        if hasattr(field, "queryset"):
            related_model = field.queryset.model
            if hasattr(related_model, "workshop"):
                field.queryset = field.queryset.filter(workshop=workshop)
                if _is_mechanic(request.user) and model is PartsRequest and related_model is WorkOrder:
                    field.queryset = field.queryset.filter(jobs__participations__mechanic=request.user, jobs__participations__is_active=True).distinct()
                if _is_mechanic(request.user) and model is PartsRequest and related_model is Job:
                    field.queryset = field.queryset.filter(participations__mechanic=request.user, participations__is_active=True)
            elif related_model._meta.label == "accounts.User":
                field.queryset = related_model.objects.filter(memberships__workshop=workshop, memberships__is_active=True, is_active=True).distinct()
            elif related_model is DocumentCategory:
                field.queryset = DocumentCategory.objects.filter(is_active=True)
            elif model is PartsRequest and related_model is PartSupplierOffer:
                field.queryset = related_model.objects.filter(part__workshop=workshop).select_related("part", "supplier")
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if isinstance(obj, PartsRequest) and obj.supplier_offer_id:
            obj.supplier = str(obj.supplier_offer.supplier)
            obj.purchase_price = obj.supplier_offer.net_purchase_price
        obj.save()
        form.save_m2m()
        if isinstance(obj, Attachment) and "file" in request.FILES:
            obj.file_name = obj.file.name
            obj.save(update_fields=("file_name",))
        _audit(workshop, request.user, "update", model, obj)
        messages.success(request, _("%(title)s: changes saved.") % {"title": title})
        return redirect("fleet:workflow_list", module=module)
    return render(request, "fleet/workflow_form.html", {"form": form, "title": f"Modifica · {title}", "module": module})


@login_required
def job_action(request, pk, action):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    if request.method != "POST": return redirect("jobs")
    job = get_object_or_404(Job.objects.select_related("work_order"), pk=pk, workshop=workshop)
    now = timezone.now()
    is_supervisor = request.user.is_staff or request.user.is_superuser or request.user.department == "admin" or request.user.seniority in ("senior", "manager")
    participation = JobParticipation.objects.filter(job=job, mechanic=request.user, is_active=True).first()

    if action == "call":
        if _is_mechanic(request.user): return HttpResponseForbidden(_("Only a supervisor can call a technician."))
        mechanic = get_object_or_404(request.user.__class__, pk=request.POST.get("mechanic"), department="technician", memberships__workshop=workshop, memberships__is_active=True)
        call, created = JobCall.objects.get_or_create(workshop=workshop, job=job, mechanic=mechanic, accepted_at__isnull=True, dismissed_at__isnull=True,
            defaults={"called_by": request.user})
        if created:
            Notification.objects.create(workshop=workshop, user=mechanic, title="Chiamata su lavorazione", body=f"{job.work_order.ro_number} · {job.title}", link="/lavori/miei/", work_order=job.work_order)
        messages.success(request, _("Call sent to the technician's profile."))
        return redirect("jobs")

    if action == "accept_call":
        call = get_object_or_404(JobCall, pk=request.POST.get("call_id"), job=job, workshop=workshop, mechanic=request.user, accepted_at__isnull=True, dismissed_at__isnull=True)
        call.accepted_at = now
        call.save(update_fields=("accepted_at",))
        participation, created = JobParticipation.objects.get_or_create(workshop=workshop, job=job, mechanic=request.user, is_active=True,
            defaults={"source": "assigned", "started_at": now})
        event_type = "start" if created else None
        if participation.paused_at:
            participation.paused_at = None
            participation.save(update_fields=("paused_at",))
            event_type = "resume"
        if job.status != "in_progress":
            job.status, job.started_at = "in_progress", job.started_at or now
            job.save(update_fields=("status", "started_at", "updated_at"))
        if event_type:
            TimeEvent.objects.create(workshop=workshop, job=job, mechanic=request.user, event_type=event_type, event_at=now, note="Chiamata accettata")
        return redirect("my_jobs")

    if action == "reopen":
        if not is_supervisor: return HttpResponseForbidden(_("Only a senior technician or supervisor can reopen a completed job."))
        if job.status != "completed":
            messages.error(request, _("The job is not completed."))
        else:
            job.status, job.completed_at = "in_progress", None
            job.save(update_fields=("status", "completed_at", "updated_at"))
            TimeEvent.objects.create(workshop=workshop, job=job, mechanic=request.user, event_type="reopen", event_at=now)
            _audit(workshop, request.user, "reopen", Job, job)
        return redirect("fleet:workflow_list", module="jobs")

    if action == "start":
        if job.status in ("completed", "cancelled"): return HttpResponseForbidden(_("This job is not open."))
        participation, created = JobParticipation.objects.get_or_create(workshop=workshop, job=job, mechanic=request.user, is_active=True,
            defaults={"source": "self", "started_at": now})
        if not created and participation.paused_at:
            participation.paused_at = None
            participation.save(update_fields=("paused_at",))
            event = "resume"
        elif not created:
            messages.info(request, _("Your session for this job is already active."))
            return redirect("my_jobs" if _is_mechanic(request.user) else "jobs")
        else:
            event = "start"
        if job.status != "in_progress":
            job.status, job.started_at = "in_progress", job.started_at or now
            job.save(update_fields=("status", "started_at", "updated_at"))
        TimeEvent.objects.create(workshop=workshop, job=job, mechanic=request.user, event_type=event, event_at=now)
    elif action == "pause" and participation and not participation.paused_at:
        reason = get_object_or_404(PauseReason, pk=request.POST.get("pause_reason"), is_active=True)
        participation.paused_at = now
        participation.save(update_fields=("paused_at",))
        TimeEvent.objects.create(workshop=workshop, job=job, mechanic=request.user, event_type="pause", pause_reason=reason, event_at=now)
        if not JobParticipation.objects.filter(job=job, is_active=True, paused_at__isnull=True).exists():
            job.status = "paused"
            job.save(update_fields=("status", "updated_at"))
    elif action in ("resume",) and participation and participation.paused_at:
        participation.paused_at = None
        participation.save(update_fields=("paused_at",))
        job.status = "in_progress"
        job.save(update_fields=("status", "updated_at"))
        TimeEvent.objects.create(workshop=workshop, job=job, mechanic=request.user, event_type="resume", event_at=now)
    elif action == "complete" and participation:
        participation.is_active, participation.finished_at, participation.paused_at = False, now, None
        participation.save(update_fields=("is_active", "finished_at", "paused_at"))
        TimeEvent.objects.create(workshop=workshop, job=job, mechanic=request.user, event_type="finish", event_at=now)
        if not JobParticipation.objects.filter(job=job, is_active=True).exists():
            job.status, job.completed_at = "completed", now
            job.save(update_fields=("status", "completed_at", "updated_at"))
        elif not JobParticipation.objects.filter(job=job, is_active=True, paused_at__isnull=True).exists():
            job.status = "paused"
            job.save(update_fields=("status", "updated_at"))
    else:
        messages.error(request, _("This action is not valid for your job session status."))
    _audit(workshop, request.user, action, Job, job)
    return redirect("my_jobs" if _is_mechanic(request.user) else "jobs")


@login_required
def my_jobs(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    calls = JobCall.objects.filter(workshop=workshop, mechanic=request.user, accepted_at__isnull=True,
        dismissed_at__isnull=True).select_related("job", "job__work_order", "called_by")
    participations = JobParticipation.objects.filter(workshop=workshop, mechanic=request.user,
        is_active=True).select_related("job", "job__work_order")
    return render(request, "fleet/my_jobs.html", {"calls": calls, "participations": participations,
        "pause_reasons": PauseReason.objects.filter(is_active=True)})


@login_required
def parts_request_action(request, pk, action):
    if _forbidden_for_mechanic(request): return _forbidden_for_mechanic(request)
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    if request.method == "POST" and action == "deliver":
        with transaction.atomic():
            item = get_object_or_404(PartsRequest.objects.select_for_update(), pk=pk, workshop=workshop)
            qty = item.quantity_delivered or item.quantity_requested
            if item.part_id and not item.inventory_applied:
                part = Part.objects.select_for_update().get(pk=item.part_id, workshop=workshop)
                if part.quantity < qty * item.conversion_factor:
                    messages.error(request, _("Insufficient stock: the issue was not recorded."))
                    return redirect("fleet:workflow_list", module="requests")
                part.quantity -= qty * item.conversion_factor
                part.save(update_fields=("quantity", "updated_at"))
                PartMovement.objects.create(workshop=workshop, part=part, work_order=item.work_order,
                    movement_type="out", quantity=qty * item.conversion_factor, unit_cost=part.cost_price,
                    note=f"Prelievo richiesta #{item.pk}", created_by=request.user)
            item.inventory_applied = True
            if item.status != "delivered":
                item.quantity_delivered = qty
                item.status, item.delivered_at, item.delivered_by = "delivered", timezone.now(), request.user
                _audit(workshop, request.user, "deliver", PartsRequest, item)
            item.save()
    return redirect("fleet:workflow_list", module="requests")


@login_required
def workflow_status_action(request, module, pk):
    if module not in ("orders", "requests") and _forbidden_for_mechanic(request):
        return _forbidden_for_mechanic(request)
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    model = {"orders": WorkOrder, "requests": PartsRequest, "claims": WarrantyClaim, "returns": WarrantyReturn}.get(module)
    if model is None or request.method != "POST": return redirect("home")
    obj = get_object_or_404(model, pk=pk, workshop=workshop)
    status_field = model._meta.get_field("status")
    allowed = {value for value, _ in status_field.choices}
    new_status = request.POST.get("status")
    if module == "orders" and _is_mechanic(request.user) and new_status not in ("open", "in_progress", "ready_inspection", "additional_work"):
        return HttpResponseForbidden(_("Administrative work order closure is restricted to reception staff."))
    if new_status not in allowed:
        messages.error(request, _("Invalid status."))
        return redirect("fleet:workflow_list", module=module)
    obj.status = new_status
    if isinstance(obj, WorkOrder) and new_status == "completed" and obj.completed_at is None:
        obj.completed_at = timezone.now()
    if isinstance(obj, WarrantyClaim):
        obj.decision_notes = request.POST.get("decision_notes", "")
        obj.approved_hours = request.POST.get("approved_hours") or None
        obj.decided_by, obj.decided_at = request.user, timezone.now()
        if obj.work_order_id:
            obj.work_order.warranty_status = new_status if new_status in dict(WorkOrder.WARRANTY_CHOICES) else "pending"
            obj.work_order.save(update_fields=("warranty_status", "updated_at"))
        if obj.requested_by_id:
            Notification.objects.create(workshop=workshop, user=obj.requested_by, title="Aggiornamento garanzia", body=new_status, work_order=obj.work_order)
    elif isinstance(obj, WarrantyReturn):
        obj.decision_notes = request.POST.get("decision_notes", "")
        obj.decided_by, obj.decided_at = request.user, timezone.now()
    obj.save()
    _audit(workshop, request.user, "status", model, obj, new_status)
    return redirect("fleet:workflow_list", module=module)


@login_required
def work_order_report(request, pk):
    if _is_mechanic(request.user):
        return HttpResponseForbidden(_("The billing report is restricted to office staff."))
    if request.method != "POST":
        return redirect("orders")
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    order = get_object_or_404(
        WorkOrder.objects.select_related("customer", "vehicle"),
        pk=pk, workshop=workshop, status="completed",
    )

    # ReportLab Platypus genera un PDF multipagina che il browser può visualizzare e stampare.
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportSubtitle", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9, textColor=colors.HexColor("#536579")))
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="RightCell", parent=styles["SmallCell"], alignment=TA_RIGHT))
    currency = workshop.currency or "EUR"

    def paragraph(value, style="BodyText"):
        safe = escape(str(value if value not in (None, "") else "—")).replace("\n", "<br/>")
        return Paragraph(safe, styles[style])

    def labelled(label, values, style="BodyText"):
        lines = values if isinstance(values, (tuple, list)) else [values]
        body = "<br/>".join(escape(str(value)) for value in lines if value not in (None, "")) or "—"
        return Paragraph(f"<b>{escape(label)}</b><br/>{body}", styles[style])

    def money(value):
        return f"{value:.2f} {currency}"

    def page_footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#536579"))
        canvas.drawString(18 * mm, 12 * mm, f"RVKeeper · {workshop.name} · Prospetto non fiscale")
        canvas.drawRightString(192 * mm, 12 * mm, f"Pagina {document.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                            topMargin=17 * mm, bottomMargin=20 * mm,
                            title=f"Prospetto OdL {order.ro_number}", author="RVKeeper")
    story = [
        Paragraph("PROSPETTO PER FATTURAZIONE", styles["Title"]),
        Paragraph("Documento riepilogativo non fiscale · non sostituisce fattura o ricevuta", styles["ReportSubtitle"]),
        Spacer(1, 8 * mm),
    ]

    customer = order.customer
    customer_name = str(customer) if customer else order.customer_name
    customer_lines = [customer_name or "Cliente non indicato"]
    if customer:
        if customer.address: customer_lines.append(customer.address)
        locality = " ".join(value for value in (customer.postal_code, customer.city) if value)
        if locality: customer_lines.append(locality)
        if customer.tax_code: customer_lines.append(f"Codice fiscale: {customer.tax_code}")
        if customer.vat_number: customer_lines.append(f"Partita IVA: {customer.vat_number}")
        if customer.phone: customer_lines.append(f"Telefono: {customer.phone}")
        if customer.email: customer_lines.append(customer.email)
    vehicle = order.vehicle
    vehicle_label = " ".join(filter(None, (vehicle.brand, vehicle.model))) if vehicle else " ".join(filter(None, (order.make, order.model)))
    vehicle_details = [vehicle_label or "Veicolo non indicato"]
    plate = vehicle.plate if vehicle else ""
    vin = vehicle.vin if vehicle else ""
    if plate: vehicle_details.append(f"Targa: {plate}")
    if vin: vehicle_details.append(f"Telaio: {vin}")
    if order.odometer is not None: vehicle_details.append(f"Km: {order.odometer}")

    info = Table([
        [labelled("Officina", workshop.name), labelled("Ordine di lavoro", [f"N. {order.ro_number}", f"Aperto il {timezone.localtime(order.created_at).strftime('%d/%m/%Y')}"])],
        [labelled("Cliente", customer_lines), labelled("Veicolo", vehicle_details)],
        [labelled("Chiuso il", timezone.localtime(order.completed_at).strftime("%d/%m/%Y %H:%M") if order.completed_at else "—"), labelled("Richiesta / diagnosi", order.reception_notes or "—")],
    ], colWidths=(86 * mm, 86 * mm), hAlign="LEFT")
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F6FA")),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#C9D5E1")),
        ("INNERGRID", (0, 0), (-1, -1), .35, colors.HexColor("#D6E0E9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([info, Spacer(1, 7 * mm), Paragraph("Interventi e manodopera", styles["Heading2"])])

    jobs = list(order.jobs.all())
    job_rows = [[paragraph("Intervento", "SmallCell"), paragraph("Stato", "SmallCell"), paragraph("Ore", "RightCell"), paragraph("Importo", "RightCell")]]
    total_minutes = 0
    for job in jobs:
        minutes = _job_minutes(job)
        total_minutes += minutes
        job_rows.append([labelled(job.title, job.description or "", "SmallCell"),
                         paragraph(job.get_status_display(), "SmallCell"),
                         paragraph(f"{minutes / 60:.2f}", "RightCell"),
                         paragraph("Da definire", "RightCell")])
    if not jobs:
        job_rows.append([paragraph("Nessun lavoro registrato", "SmallCell"), paragraph("—", "SmallCell"), paragraph("0,00", "RightCell"), paragraph("—", "RightCell")])
    job_table = LongTable(job_rows, colWidths=(89 * mm, 27 * mm, 25 * mm, 31 * mm), repeatRows=1)
    job_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8F2")),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#C9D5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([job_table, Spacer(1, 3 * mm), paragraph(f"Tempo consuntivo totale: {total_minutes / 60:.2f} ore", "RightCell"), Spacer(1, 5 * mm), Paragraph("Ricambi utilizzati", styles["Heading2"])])

    requests = list(order.parts_requests.filter(status="delivered").select_related("part"))
    part_rows = [[paragraph("Articolo", "SmallCell"), paragraph("Quantità", "RightCell"), paragraph("Prezzo unitario", "RightCell"), paragraph("Importo", "RightCell")]]
    parts_total = 0
    for item in requests:
        quantity = item.quantity_delivered or item.quantity_requested
        name = str(item.part) if item.part_id else item.custom_item
        unit_price = item.part.sale_price if item.part_id else None
        line_total = quantity * unit_price if unit_price is not None else None
        if line_total is not None:
            parts_total += line_total
        part_rows.append([paragraph(name, "SmallCell"), paragraph(f"{quantity} {item.unit_delivered or item.unit}", "RightCell"),
                          paragraph(money(unit_price) if unit_price is not None else "Da definire", "RightCell"),
                          paragraph(money(line_total) if line_total is not None else "Da definire", "RightCell")])
    if not requests:
        part_rows.append([paragraph("Nessun ricambio registrato come consegnato", "SmallCell"), paragraph("—", "RightCell"), paragraph("—", "RightCell"), paragraph("—", "RightCell")])
    part_table = LongTable(part_rows, colWidths=(83 * mm, 29 * mm, 35 * mm, 25 * mm), repeatRows=1)
    part_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8F2")),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#C9D5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    total = Table([[paragraph("Totale parziale ricambi a listino", "RightCell"), paragraph(money(parts_total), "RightCell")]], colWidths=(141 * mm, 31 * mm), hAlign="RIGHT")
    total.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), .8, colors.HexColor("#12263D")), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    story.extend([part_table, Spacer(1, 2 * mm), total, Spacer(1, 8 * mm),
                  paragraph("Manodopera indicata in ore consuntive; valorizzazione e imposte saranno determinate in fase di fatturazione.", "SmallCell")])
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    pdf_data = buffer.getvalue()

    if request.POST.get("mark_invoiced") == "1":
        with transaction.atomic():
            locked_order = WorkOrder.objects.select_for_update().get(pk=order.pk, workshop=workshop)
            if not locked_order.invoiced:
                locked_order.invoiced = True
                locked_order.invoiced_at = timezone.now()
                locked_order.invoiced_by = request.user
                locked_order.save(update_fields=("invoiced", "invoiced_at", "invoiced_by", "updated_at"))
                _audit(workshop, request.user, "invoiced", WorkOrder, locked_order, "Rapportino contrassegnato come fatturato")

    response = HttpResponse(pdf_data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="prospetto-odl-{order.pk}.pdf"'
    return response


@login_required
def mark_notifications_read(request):
    workshop = _workshop_or_redirect(request)
    if request.method == "POST" and workshop:
        Notification.objects.filter(workshop=workshop).filter(models.Q(user=request.user) | models.Q(user__isnull=True), read=False).update(read=True)
    return redirect("fleet:notifications")


@login_required
def report(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    time_by_mechanic = {}
    total_minutes = 0
    for job in Job.objects.filter(workshop=workshop).prefetch_related("time_events__mechanic"):
        running, seconds_by_user = {}, {}
        for event in job.time_events.order_by("event_at", "pk"):
            key = event.mechanic_id
            if event.event_type in ("start", "resume"):
                running[key] = event.event_at
            elif event.event_type in ("pause", "finish", "waiting") and key in running:
                seconds_by_user[key] = seconds_by_user.get(key, 0) + max(0, (event.event_at - running.pop(key)).total_seconds())
        for key, started in running.items():
            seconds_by_user[key] = seconds_by_user.get(key, 0) + max(0, (timezone.now() - started).total_seconds())
        for key, seconds in seconds_by_user.items():
            minutes = int(seconds // 60)
            time_by_mechanic[key] = time_by_mechanic.get(key, 0) + minutes
            total_minutes += minutes
    users = request.user.__class__.objects.in_bulk(time_by_mechanic.keys())
    technician_rows = [{"mechanic": users.get(key), "minutes": value} for key, value in time_by_mechanic.items()]
    return render(request, "fleet/report.html", {
        "orders": WorkOrder.objects.filter(workshop=workshop).values("status").annotate(total=Count("id")),
        "jobs": Job.objects.filter(workshop=workshop).values("status").annotate(total=Count("id")),
        "technician_time": technician_rows,
        "total_minutes": total_minutes,
        "open_requests": PartsRequest.objects.filter(workshop=workshop).exclude(status__in=("delivered", "cancelled")).count(),
    })


@login_required
def notifications(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    items = Notification.objects.filter(workshop=workshop).filter(models.Q(user=request.user) | models.Q(user__isnull=True))
    return render(request, "fleet/notifications.html", {"items": items})


@login_required
def audit_log(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    return render(request, "fleet/audit_log.html", {"items": AuditLog.objects.filter(workshop=workshop).select_related("actor", "work_order")[:300]})


@login_required
def data_export(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    models_to_export = (Workshop, Role, Membership, CamperOwner, Camper, CamperPhoto, WorkOrder, Job, Quote, QuoteLine, Part, PartMovement,
                        PartSupplierOffer, PartDocument,
                        PartsRequest, WarrantyClaim, WarrantyReturn, JobNote,
                        Attachment, Notification, TimeEvent, JobAssignment, AuditLog)
    querysets = [model.objects.filter(pk=workshop.pk) if model is Workshop
                 else model.objects.filter(part__workshop=workshop) if model in (PartSupplierOffer, PartDocument)
                 else model.objects.filter(quote__workshop=workshop) if model is QuoteLine
                 else model.objects.filter(workshop=workshop) if any(f.name == "workshop" for f in model._meta.fields)
                 else model.objects.filter(camper__workshop=workshop) for model in models_to_export]
    payload = serializers.serialize("json", [obj for queryset in querysets for obj in queryset])
    response = HttpResponse(payload, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="rvkeeper-{workshop.slug}-backup.json"'
    return response
