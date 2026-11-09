from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Count, Sum
from django.forms import modelform_factory
from django.core import serializers
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from workshops.models import Membership
from workshops.models import Role, Workshop
from .forms import CamperForm
from .models import (Attachment, AuditLog, Camper, CamperOwner, CamperPhoto, Job,
                     JobAssignment, JobNote, Notification, Part, PartsRequest,
                     TimeEvent, WarrantyClaim, WarrantyReturn, WorkOrder)


def _active_workshop(user):
    membership = Membership.objects.filter(
        user=user, is_active=True, workshop__is_active=True
    ).select_related("workshop").first()
    return membership.workshop if membership else None


@login_required
def camper_list(request):
    workshop = _active_workshop(request.user)
    campers = Camper.objects.filter(workshop=workshop, is_active=True) if workshop else Camper.objects.none()
    return render(request, "fleet/camper_list.html", {"campers": campers, "has_workshop": workshop is not None})


@login_required
def camper_create(request):
    workshop = _active_workshop(request.user)
    if workshop is None:
        messages.error(request, "Il tuo account non è associato a un'officina attiva.")
        return redirect("fleet:camper_list")

    form = CamperForm(request.POST or None, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        camper = form.save(commit=False)
        camper.workshop = workshop
        camper.save()
        messages.success(request, "Camper aggiunto al parco mezzi.")
        return redirect("fleet:camper_list")
    return render(request, "fleet/camper_form.html", {"form": form})


MODULES = {
    "orders": (WorkOrder, "Ordini di lavoro", ("ro_number", "customer_name", "status", "created_at")),
    "jobs": (Job, "Lavori e tecnici", ("work_order", "title", "assigned_to", "status")),
    "parts": (Part, "Magazzino ricambi", ("part_number", "name", "quantity", "min_stock", "location")),
    "requests": (PartsRequest, "Richieste ricambi", ("work_order", "part", "custom_item", "quantity_requested", "status")),
    "claims": (WarrantyClaim, "Garanzie", ("work_order", "component", "problem_description", "status")),
    "returns": (WarrantyReturn, "Resi in garanzia", ("work_order", "part_name", "quantity", "status")),
    "attachments": (Attachment, "Allegati", ("work_order", "file_name", "caption", "uploaded_by", "created_at")),
    "notes": (JobNote, "Note interventi", ("job", "author", "language", "text", "created_at")),
    "assignments": (JobAssignment, "Assegnazioni tecnici", ("job", "from_technician", "to_technician", "reason", "created_at")),
}
FORM_EXCLUDES = {
    WorkOrder: ("workshop", "created_by", "created_at", "updated_at"),
    Job: ("workshop", "status", "active_technician", "net_minutes", "waiting_minutes", "started_at", "completed_at", "active_since", "waiting_started_at", "created_at", "updated_at"),
    Part: ("workshop", "created_at", "updated_at"),
    PartsRequest: ("workshop", "requested_by", "delivered_at", "delivered_by", "inventory_applied", "created_at", "updated_at"),
    WarrantyClaim: ("workshop", "requested_by", "decided_by", "decided_at", "created_at", "updated_at"),
    WarrantyReturn: ("workshop", "requested_by", "decided_by", "decided_at", "created_at"),
    Attachment: ("workshop", "uploaded_by", "created_at"),
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
        messages.error(request, "Il tuo account non è associato a un'officina attiva.")
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


@login_required
def dashboard(request):
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
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    model, title, columns = _module(module)
    objects = model.objects.filter(workshop=workshop).select_related(*[f for f in columns if f in {x.name for x in model._meta.fields} and model._meta.get_field(f).is_relation])
    if model is PartsRequest:
        objects = objects.select_related("work_order", "part")
    if model is WarrantyClaim or model is WarrantyReturn:
        objects = objects.select_related("work_order")
    if model is Job:
        objects = objects.select_related("work_order", "assigned_to")
    if model is Attachment:
        objects = objects.select_related("work_order", "uploaded_by")
    if module == "parts":
        for part in objects.filter(quantity__lte=models.F("min_stock")):
            Notification.objects.get_or_create(workshop=workshop, user=None, title="Scorta ricambi bassa", link=f"/magazzino/", read=False, defaults={"body": f"{part.part_number} · {part.name}: disponibili {part.quantity}, minimo {part.min_stock}"})
    display_rows = []
    for obj in objects:
        values = []
        for name in columns:
            if name == "custom_item" and getattr(obj, "part_id", None):
                value = ""
            else:
                field = model._meta.get_field(name)
                if field.is_relation:
                    value = str(getattr(obj, name) or "—")
                elif field.choices:
                    value = getattr(obj, f"get_{name}_display")()
                else:
                    value = getattr(obj, name)
                if isinstance(obj, JobNote) and name == "text":
                    value = obj.translations.get(request.user.preferred_language) or value
            values.append(value)
        display_rows.append((obj, values))
    context = {"module": module, "title": title, "objects": objects, "columns": columns, "display_rows": display_rows, "model": model,
               "status_choices": model._meta.get_field("status").choices if any(f.name == "status" for f in model._meta.fields) else ()}
    return render(request, "fleet/workflow_list.html", context)


@login_required
def workflow_create(request, module):
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    model, title, _ = _module(module)
    exclude = FORM_EXCLUDES[model]
    Form = modelform_factory(model, exclude=exclude)
    form = Form(request.POST or None, request.FILES or None)
    for field in form.fields.values():
        if hasattr(field, "queryset"):
            related_model = field.queryset.model
            if hasattr(related_model, "workshop"):
                field.queryset = field.queryset.filter(workshop=workshop)
            elif related_model._meta.label == "accounts.User":
                field.queryset = related_model.objects.filter(memberships__workshop=workshop, memberships__is_active=True, is_active=True).distinct()
    if model is Attachment and "file" in form.fields:
        form.fields["file"].required = True
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.workshop = workshop
        if isinstance(obj, WorkOrder): obj.created_by = request.user
        if isinstance(obj, PartsRequest): obj.requested_by = request.user
        if isinstance(obj, WarrantyClaim): obj.requested_by = request.user
        if isinstance(obj, WarrantyReturn): obj.requested_by = request.user
        if isinstance(obj, JobNote):
            obj.author = request.user
            obj.language = request.user.preferred_language
            obj.translations = {}
            try:
                from deep_translator import GoogleTranslator
                for language, _ in request.user.LANGUAGE_CHOICES:
                    if language != obj.language:
                        try:
                            obj.translations[language] = GoogleTranslator(source=obj.language[:2], target=language[:2]).translate(obj.text) or ""
                        except Exception:
                            continue
            except ImportError:
                pass
        if isinstance(obj, JobAssignment) and obj.to_technician_id:
            obj.from_technician = Job.objects.filter(pk=obj.job_id).values_list("assigned_to_id", flat=True).first()
        if isinstance(obj, Attachment):
            obj.uploaded_by = request.user
            obj.file_name = obj.file.name
        obj.save()
        form.save_m2m()
        if isinstance(obj, JobAssignment) and obj.to_technician_id:
            Job.objects.filter(pk=obj.job_id, workshop=workshop).update(assigned_to=obj.to_technician)
        _audit(workshop, request.user, "create", model, obj)
        messages.success(request, f"{title}: elemento creato.")
        return redirect("fleet:workflow_list", module=module)
    return render(request, "fleet/workflow_form.html", {"form": form, "title": title, "module": module})


@login_required
def workflow_edit(request, module, pk):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    model, title, _ = _module(module)
    obj = get_object_or_404(model, pk=pk, workshop=workshop)
    Form = modelform_factory(model, exclude=FORM_EXCLUDES[model])
    form = Form(request.POST or None, request.FILES or None, instance=obj)
    for field in form.fields.values():
        if hasattr(field, "queryset"):
            related_model = field.queryset.model
            if hasattr(related_model, "workshop"):
                field.queryset = field.queryset.filter(workshop=workshop)
            elif related_model._meta.label == "accounts.User":
                field.queryset = related_model.objects.filter(memberships__workshop=workshop, memberships__is_active=True, is_active=True).distinct()
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        if isinstance(obj, Attachment) and "file" in request.FILES:
            obj.file_name = obj.file.name
            obj.save(update_fields=("file_name",))
        _audit(workshop, request.user, "update", model, obj)
        messages.success(request, f"{title}: modifiche salvate.")
        return redirect("fleet:workflow_list", module=module)
    return render(request, "fleet/workflow_form.html", {"form": form, "title": f"Modifica · {title}", "module": module})


@login_required
def job_action(request, pk, action):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    job = get_object_or_404(Job, pk=pk, workshop=workshop)
    if request.method != "POST": return redirect("fleet:workflow_list", module="jobs")
    now = timezone.now()
    if action == "start" and job.status in ("not_started", "paused", "waiting_parts", "waiting_warranty"):
        if job.waiting_started_at:
            job.waiting_minutes += max(0, int((now - job.waiting_started_at).total_seconds() / 60))
            job.waiting_started_at = None
        job.status, job.active_since, job.started_at, job.active_technician = "in_progress", now, job.started_at or now, request.user
    elif action in ("pause", "complete") and job.status == "in_progress":
        elapsed = max(0, int((now - job.active_since).total_seconds() / 60)) if job.active_since else 0
        job.net_minutes += elapsed
        job.active_since = None
        job.status = "paused" if action == "pause" else "completed"
        if action == "complete": job.completed_at = now
    elif action in ("waiting_parts", "waiting_warranty") and job.status not in ("completed", "cancelled"):
        if job.status == "in_progress" and job.active_since:
            job.net_minutes += max(0, int((now - job.active_since).total_seconds() / 60))
        job.status, job.block_reason, job.waiting_started_at, job.active_since = action, request.POST.get("reason", ""), now, None
    else:
        messages.error(request, "Azione non valida per lo stato attuale del lavoro.")
        return redirect("fleet:workflow_list", module="jobs")
    job.save()
    TimeEvent.objects.create(workshop=workshop, job=job, mechanic=request.user, event_type="finish" if action == "complete" else "pause" if action == "pause" else "waiting" if action.startswith("waiting") else "start", event_at=now, note=request.POST.get("reason", ""))
    _audit(workshop, request.user, action, Job, job)
    return redirect("fleet:workflow_list", module="jobs")


@login_required
def parts_request_action(request, pk, action):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    if request.method == "POST" and action == "deliver":
        with transaction.atomic():
            item = get_object_or_404(PartsRequest.objects.select_for_update(), pk=pk, workshop=workshop)
            qty = item.quantity_delivered or item.quantity_requested
            if item.part_id and not item.inventory_applied:
                part = Part.objects.select_for_update().get(pk=item.part_id, workshop=workshop)
                part.quantity -= qty * item.conversion_factor
                part.save(update_fields=("quantity", "updated_at"))
            item.inventory_applied = True
            if item.status != "delivered":
                item.quantity_delivered = qty
                item.status, item.delivered_at, item.delivered_by = "delivered", timezone.now(), request.user
                _audit(workshop, request.user, "deliver", PartsRequest, item)
            item.save()
    return redirect("fleet:workflow_list", module="requests")


@login_required
def workflow_status_action(request, module, pk):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    model = {"orders": WorkOrder, "requests": PartsRequest, "claims": WarrantyClaim, "returns": WarrantyReturn}.get(module)
    if model is None or request.method != "POST": return redirect("home")
    obj = get_object_or_404(model, pk=pk, workshop=workshop)
    status_field = model._meta.get_field("status")
    allowed = {value for value, _ in status_field.choices}
    new_status = request.POST.get("status")
    if new_status not in allowed:
        messages.error(request, "Stato non valido.")
        return redirect("fleet:workflow_list", module=module)
    obj.status = new_status
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
def mark_notifications_read(request):
    workshop = _workshop_or_redirect(request)
    if request.method == "POST" and workshop:
        Notification.objects.filter(workshop=workshop).filter(models.Q(user=request.user) | models.Q(user__isnull=True), read=False).update(read=True)
    return redirect("fleet:notifications")


@login_required
def report(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    return render(request, "fleet/report.html", {
        "orders": WorkOrder.objects.filter(workshop=workshop).values("status").annotate(total=Count("id")),
        "jobs": Job.objects.filter(workshop=workshop).values("status").annotate(total=Count("id")),
        "technician_time": Job.objects.filter(workshop=workshop).values("active_technician__email").annotate(minutes=Sum("net_minutes")),
        "total_minutes": Job.objects.filter(workshop=workshop).aggregate(total=Sum("net_minutes"))["total"] or 0,
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
    models_to_export = (Workshop, Role, Membership, CamperOwner, Camper, CamperPhoto, WorkOrder, Job, Part,
                        PartsRequest, WarrantyClaim, WarrantyReturn, JobNote,
                        Attachment, Notification, TimeEvent, JobAssignment, AuditLog)
    querysets = [model.objects.filter(pk=workshop.pk) if model is Workshop
                 else model.objects.filter(workshop=workshop) if any(f.name == "workshop" for f in model._meta.fields)
                 else model.objects.filter(camper__workshop=workshop) for model in models_to_export]
    payload = serializers.serialize("json", [obj for queryset in querysets for obj in queryset])
    response = HttpResponse(payload, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="rvkeeper-{workshop.slug}-backup.json"'
    return response
