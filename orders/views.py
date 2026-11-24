"""Viste per ordini, lavorazioni e flussi operativi collegati."""

import logging
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Exists, OuterRef, Sum
from django.forms import modelform_factory
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from clientandsuppliers.models import CamperOwner
from fleet.forms import (
    CamperForm,
    CamperPhotoForm,
    InvoiceLaborPriceFormSet,
    InvoicePartsRequestFormSet,
    InvoiceUsagePriceFormSet,
    PartsRequestFormSet,
    PartsUsageFormSet,
    TimeReportFilterForm,
    WorkOrderForm,
)
from fleet.models import Camper, CamperPhoto
from orders.time_reporting import build_time_report, export_time_report_excel, export_time_report_pdf
from orders.models import (
    Attachment,
    AuditLog,
    BillOfMaterials,
    BillOfMaterialsLine,
    DocumentCategory,
    Job,
    JobAssignment,
    JobCall,
    JobNote,
    JobParticipation,
    LaborArticle,
    Notification,
    PauseReason,
    PriceList,
    PriceListItem,
    TimeEvent,
    WarrantyClaim,
    WarrantyReturn,
    WorkOrder,
    next_ro_number,
)
from orders.pricing import resolve_item_price
from parts.models import (
    JobPartUsage,
    Part,
    PartDocument,
    PartMovement,
    PartSupplierOffer,
    PartsRequest,
    TransferSlipLine,
    WarehouseNote,
    WarehouseNoteRead,
)
from parts.services import (
    InsufficientStockError,
    add_request_to_purchase_order,
    cancel_transfer_slip,
    close_transfer_slip,
    reserve_job_usage,
    reserve_parts_request,
)
from quotes.models import Quote, QuoteLine
from workshops.models import Membership, Workshop

from .forms import (
    BillOfMaterialsForm,
    BillOfMaterialsLineFormSet,
    CustomerItemDiscountFormSet,
    LaborArticleListEntryFormSet,
    PriceListForm,
    PriceListItemFormSet,
)
from .models import CustomerItemDiscount
from .pricing import ensure_workshop_price_list, rotate_price_list_prices


logger = logging.getLogger(__name__)
CUSTOMER_APPROVAL_THRESHOLD = Decimal("100.00")

MODULES = {
    "orders": (WorkOrder, _("Work orders"), ("ro_number", "vehicle", "customer", "customer_phone", "status", "completed_at", "invoiced")),
    "jobs": (Job, _("Jobs and technicians"), ("work_order", "title", "department", "status")),
    "requests": (
        PartsRequest,
        _("Parts requests"),
        (
            "work_order", "part", "supplier_offer", "custom_item", "quantity_requested",
            "status", "approval_status", "customer_quoted_price", "repair_minutes",
        ),
    ),
    "claims": (WarrantyClaim, _("Warranty claims"), ("work_order", "component", "problem_description", "status")),
    "returns": (WarrantyReturn, _("Warranty returns"), ("work_order", "part_name", "quantity", "status")),
    "attachments": (Attachment, _("Attachments"), ("work_order", "category", "file_name", "caption", "uploaded_by", "created_at")),
    "notes": (JobNote, _("Job notes"), ("job", "author", "language", "text", "created_at")),
    "assignments": (JobAssignment, _("Technician assignments"), ("job", "from_technician", "to_technician", "reason", "created_at")),
}

FORM_EXCLUDES = {
    WorkOrder: ("workshop", "status", "created_by", "completed_at", "invoiced", "invoiced_at", "invoiced_by", "created_at", "updated_at"),
    Job: ("workshop", "status", "started_at", "completed_at", "created_at", "updated_at"),
    PartsRequest: (
        "workshop", "requested_by", "quantity_delivered", "purchase_price", "delivered_at",
        "delivered_by", "inventory_applied", "status", "approval_status",
        "customer_approval_recorded_at", "customer_approval_recorded_by", "approval_decided_at",
        "approval_decided_by", "warehouse_eta_kind", "warehouse_eta_value",
        "warehouse_eta_updated_at", "warehouse_eta_updated_by", "warehouse_reminder_sent_at",
        "warehouse_reminder_answered_at", "created_at", "updated_at",
    ),
    WarrantyClaim: ("workshop", "requested_by", "decided_by", "decided_at", "created_at", "updated_at"),
    WarrantyReturn: ("workshop", "requested_by", "decided_by", "decided_at", "created_at"),
    Attachment: ("workshop", "file_name", "uploaded_by", "created_at"),
    JobNote: ("workshop", "author", "created_at"),
    JobAssignment: ("workshop", "created_at"),
}

def _active_workshop(user):
    membership = Membership.objects.filter(
        user=user, is_active=True, workshop__is_active=True
    ).select_related("workshop").first()
    return membership.workshop if membership else None


def _is_mechanic(user):
    return getattr(user, "profile", "") == "mechanic"


def _forbidden_for_mechanic(request):
    if _is_mechanic(request.user):
        return HttpResponseForbidden(_("Your profile can only access work orders and parts."))
    if getattr(request.user, "profile", "") == "warehouse" and not request.path.startswith(("/magazzino/", "/richieste-ricambi/")):
        return HttpResponseForbidden(_("Your profile can only manage warehouse inventory and parts requests."))
    return None


def _can_manage_parts(user):
    return user.is_administrator or user.is_warehouse


def _can_approve_parts(user):
    return user.is_administrator


def _notify_profile(workshop, profile, title, body, link, work_order):
    recipients = list(get_user_model().objects.filter(
        profile=profile,
        is_active=True,
        memberships__workshop=workshop,
        memberships__is_active=True,
    ).distinct())
    notifications = [
        Notification(
            workshop=workshop,
            user=recipient,
            title=str(title),
            body=body,
            link=link,
            work_order=work_order,
        )
        for recipient in recipients
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)
    else:
        Notification.objects.create(
            workshop=workshop,
            title=str(title),
            body=body,
            link=link,
            work_order=work_order,
        )


def _notify_requester(item, title, body):
    if item.requested_by_id:
        Notification.objects.create(
            workshop=item.workshop,
            user=item.requested_by,
            title=str(title),
            body=body,
            link="/lavori/miei/",
            work_order=item.work_order,
        )


def _create_warehouse_note(item, author, text, estimated_delivery_at=None):
    note = WarehouseNote.objects.create(
        workshop=item.workshop,
        work_order=item.work_order,
        parts_request=item,
        part=item.part,
        author=author,
        text=text,
        estimated_delivery_at=estimated_delivery_at,
    )
    recipient_ids = set()
    if item.job_id:
        recipient_ids.update(
            JobParticipation.objects.filter(
                workshop=item.workshop,
                job_id=item.job_id,
                mechanic__profile="mechanic",
            ).values_list("mechanic_id", flat=True).distinct()
        )
    if item.requested_by_id:
        recipient_ids.add(item.requested_by_id)
    if recipient_ids:
        WarehouseNoteRead.objects.bulk_create(
            [WarehouseNoteRead(note=note, recipient_id=user_id) for user_id in recipient_ids],
            ignore_conflicts=True,
        )
    logger.info(
        "Nota di magazzino inviata al meccanico",
        extra={
            "work_order_id": item.work_order_id,
            "activity_id": item.job_id,
            "part_id": item.part_id,
            "parts_request_id": item.pk,
            "note_id": note.pk,
            "user_id": author.pk,
        },
    )
    return note


def _parts_request_quote(part, quantity, customer=None):
    if not part:
        return None
    unit_price = resolve_item_price(customer, part=part)["total_unit_price"]
    return (unit_price * quantity).quantize(Decimal("0.01")) if unit_price is not None else None


def _set_initial_parts_request_status(item):
    quote = _parts_request_quote(item.part, item.quantity_requested, item.work_order.customer)
    item.customer_quoted_price = quote
    item.status = "pending"
    item.approval_status = (
        "awaiting_customer"
        if quote is not None and quote > CUSTOMER_APPROVAL_THRESHOLD
        else "not_required"
    )


def _notify_new_parts_requests(requests):
    customer_approval_requests = [item for item in requests if item.approval_status == "awaiting_customer"]
    warehouse_requests = [item for item in requests if item.approval_status == "not_required"]
    for items, profile, title in (
        (customer_approval_requests, "admin", _("Customer approval required")),
        (warehouse_requests, "warehouse", _("Parts requested from a job")),
    ):
        if not items:
            continue
        first = items[0]
        job_label = f" · {first.job.title}" if first.job_id else ""
        details = ", ".join(
            f"{item.part} ({item.customer_quoted_price} {item.workshop.currency})"
            for item in items
        )
        _notify_profile(
            first.workshop,
            profile,
            title,
            f"{first.work_order.ro_number}{job_label} · {details}",
            "/richieste-ricambi/",
            first.work_order,
        )


@login_required
def work_order_detail(request, pk):
    workshop = _active_workshop(request.user)
    if workshop is None:
        return redirect("home")
    order = get_object_or_404(
        WorkOrder.objects.select_related("customer", "vehicle", "created_by", "invoiced_by").prefetch_related(
            "jobs__time_events", "jobs__participations__mechanic", "jobs__notes__author",
            "jobs__attachments__category", "jobs__parts_used__part", "parts_requests__part", "attachments__category",
            "warranty_claims", "warranty_returns",
        ),
        pk=pk,
        workshop=workshop,
    )
    if _is_mechanic(request.user):
        WarehouseNoteRead.objects.filter(
            note__work_order=order,
            recipient=request.user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())
    jobs = list(order.jobs.all())
    for job in jobs:
        job.actual_minutes = _job_minutes(job)
    return render(request, "orders/work_order_detail.html", {
        "order": order,
        "jobs": jobs,
        "parts_requests": order.parts_requests.select_related("part"),
        "attachments": order.attachments.select_related("category"),
        "warranty_claims": order.warranty_claims.all(),
        "warranty_returns": order.warranty_returns.all(),
        "warehouse_notes": order.warehouse_notes.select_related(
            "part", "author", "parts_request",
        ).all(),
    })


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
    if request.user.profile == "warehouse":
        return redirect("inventory")
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return render(request, "fleet/dashboard.html", {"has_workshop": False})
    if _is_mechanic(request.user):
        unread_notes = WarehouseNoteRead.objects.filter(
            note__work_order=OuterRef("pk"),
            recipient=request.user,
            read_at__isnull=True,
        )
        context = {
            "has_workshop": True,
            "is_mechanic": True,
            "my_active_sessions": JobParticipation.objects.filter(
                workshop=workshop, mechanic=request.user, is_active=True
            ).select_related("job", "job__work_order"),
            "my_pending_calls": JobCall.objects.filter(
                workshop=workshop, mechanic=request.user, accepted_at__isnull=True,
                dismissed_at__isnull=True,
            ).select_related("job", "job__work_order"),
            "open_work_orders": WorkOrder.objects.filter(
                workshop=workshop,
            ).exclude(status__in=("completed", "cancelled")).annotate(
                has_unread_warehouse_notes=Exists(unread_notes),
                has_activity=Exists(Job.objects.filter(work_order=OuterRef("pk"))),
            ).select_related("vehicle", "customer").order_by("-created_at"),
        }
        return render(request, "fleet/dashboard.html", context)
    orders = WorkOrder.objects.filter(workshop=workshop)
    jobs = Job.objects.filter(workshop=workshop)
    low_stock = Part.objects.filter(workshop=workshop, quantity__lte=models.F("min_stock"))
    context = {
        "has_workshop": True,
        "orders_open": orders.exclude(status__in=("completed", "cancelled")).count(),
        "jobs_active": jobs.filter(status="in_progress").count(),
        "requests_open": PartsRequest.objects.filter(workshop=workshop).exclude(status__in=("delivered", "cancelled")).count(),
        "low_stock_count": low_stock.count(),
        "recent_orders": orders.select_related("customer")[:8],
        "active_jobs": jobs.filter(status__in=("in_progress", "paused", "waiting_parts", "waiting_warranty")).select_related("work_order")[:8],
    }
    return render(request, "fleet/dashboard.html", context)


@login_required
def workflow_list(request, module):
    if module == "owners":
        return redirect("customers")
    if module == "parts":
        return redirect("inventory")
    if request.user.profile == "warehouse" and module != "requests":
        return HttpResponseForbidden(_("Your profile can only manage warehouse inventory and parts requests."))
    if module not in ("orders", "jobs", "parts", "requests") and _forbidden_for_mechanic(request):
        return _forbidden_for_mechanic(request)
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    model, title, columns = _module(module)
    if module == "requests" and _is_mechanic(request.user):
        columns = tuple(
            column for column in columns
            if column not in ("supplier_offer", "customer_quoted_price")
        )
    if module == "orders" and _is_mechanic(request.user):
        columns = tuple(column for column in columns if column != "invoiced")
    objects = model.objects.filter(workshop=workshop).select_related(*[f for f in columns if f in {x.name for x in model._meta.fields} and model._meta.get_field(f).is_relation])
    if module == "orders" and _is_mechanic(request.user):
        objects = objects.exclude(status__in=("completed", "cancelled"))
        unread_notes = WarehouseNoteRead.objects.filter(
            note__work_order=OuterRef("pk"),
            recipient=request.user,
            read_at__isnull=True,
        )
        objects = objects.annotate(has_unread_warehouse_notes=Exists(unread_notes))
    if model is PartsRequest:
        objects = objects.select_related("work_order", "part", "supplier_offer__supplier")
        if _is_mechanic(request.user):
            objects = objects.defer("customer_quoted_price")
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
        if module == "jobs":
            code = f"{obj.work_order.ro_number}-{obj.job_number:02d}"
        elif module == "requests":
            code = obj.order_number or f"REQ-{obj.pk:06d}"
        elif module == "claims":
            code = f"GAR-{obj.pk:06d}"
        elif module == "returns":
            code = f"RES-{obj.pk:06d}"
        elif module == "attachments":
            code = f"ATT-{obj.pk:06d}"
        elif module == "notes":
            code = f"NOT-{obj.pk:06d}"
        elif module == "assignments":
            code = f"ASG-{obj.pk:06d}"
        else:
            code = None
        if code is not None:
            values.insert(0, code)
        display_rows.append((obj, values))
    headers = {
        "orders": (_("Work order"), _("Camper"), _("Customer"), _("Customer phone"), _("Status"), _("Closed at"), _("Invoicing")),
        "jobs": (_("Code"), _("Work order"), _("Job"), _("Technician"), _("Status")),
        "requests": (
            _("Code"), _("Work order"), _("Part"), _("Supplier / price"), _("Custom item"),
            _("Requested quantity"), _("Warehouse status"), _("Approval"), _("Customer quote"), _("Repair minutes"),
        ),
        "claims": (_("Code"), _("Work order"), _("Component"), _("Problem description"), _("Status")),
        "returns": (_("Code"), _("Work order"), _("Part"), _("Quantity"), _("Status")),
        "attachments": (_("Code"), _("Work order"), _("Category"), _("File name"), _("Description"), _("Uploaded by"), _("Date")),
        "notes": (_("Code"), _("Job"), _("Author"), _("Language"), _("Note"), _("Date")),
        "assignments": (_("Code"), _("Job"), _("From"), _("To"), _("Reason"), _("Date")),
    }
    column_headers = headers.get(module, columns)
    if module == "requests" and _is_mechanic(request.user):
        column_headers = (
            _("Code"), _("Work order"), _("Part"), _("Custom item"), _("Requested quantity"),
            _("Warehouse status"), _("Approval"), _("Repair minutes"),
        )
    if module == "orders" and _is_mechanic(request.user):
        column_headers = (_("Work order number"), _("Camper"), _("Customer"), _("Phone"), _("Status"), _("Closed at"))
    context = {"module": module, "title": title, "objects": objects, "columns": columns, "headers": column_headers, "display_rows": display_rows, "model": model,
               "status_choices": model._meta.get_field("status").choices if any(f.name == "status" for f in model._meta.fields) else ()}
    context["can_manage_parts"] = _can_manage_parts(request.user)
    context["can_approve_parts"] = _can_approve_parts(request.user)
    if module == "jobs":
        context["mechanics"] = request.user.__class__.objects.filter(memberships__workshop=workshop,
            memberships__is_active=True, profile="mechanic", is_active=True).distinct().order_by(
                "last_name", "first_name", "username"
            )
        context["pause_reasons"] = PauseReason.objects.filter(is_active=True)
        context["active_job_ids"] = list(JobParticipation.objects.filter(workshop=workshop, mechanic=request.user,
            is_active=True, paused_at__isnull=True).values_list("job_id", flat=True))
        context["paused_job_ids"] = list(JobParticipation.objects.filter(workshop=workshop, mechanic=request.user,
            is_active=True, paused_at__isnull=False).values_list("job_id", flat=True))
    return render(request, "fleet/workflow_list.html", context)


@login_required
def workflow_create(request, module):
    if request.user.profile == "warehouse" and module != "requests":
        return HttpResponseForbidden(_("Your profile can only manage warehouse inventory and parts requests."))
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
    if model is PartsRequest:
        exclude = exclude + ("customer_quoted_price", "repair_minutes")
        if _is_mechanic(request.user):
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
                if related_model is LaborArticle:
                    field.queryset = field.queryset.filter(is_active=True).order_by("tariff_type", "code")
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
    if model is Job and not request.method == "POST":
        standard_article = LaborArticle.objects.filter(
            workshop=workshop, is_active=True, tariff_type="standard"
        ).order_by("code").first()
        if standard_article:
            form.initial["labor_article"] = standard_article.pk
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
        if isinstance(obj, PartsRequest):
            obj.requested_by = request.user
            _set_initial_parts_request_status(obj)
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
        if isinstance(obj, WorkOrder):
            with transaction.atomic():
                Workshop.objects.select_for_update().get(pk=workshop.pk)
                obj.ro_number = next_ro_number(workshop)
                obj.save()
                if obj.bom_template_id:
                    for line in obj.bom_template.lines.select_related("labor_article").all():
                        Job.objects.create(
                            workshop=workshop,
                            work_order=obj,
                            job_number=_next_job_number(obj),
                            title=line.title,
                            labor_article=line.labor_article,
                            description=line.description,
                            department=line.department,
                            specialty=line.specialty,
                            standard_minutes=line.standard_minutes,
                        )
        elif isinstance(obj, Job):
            with transaction.atomic():
                locked_order = WorkOrder.objects.select_for_update().get(
                    pk=obj.work_order_id, workshop=workshop,
                )
                obj.work_order = locked_order
                obj.job_number = _next_job_number(locked_order)
                obj.save()
        else:
            obj.save()
        form.save_m2m()
        if isinstance(obj, PartsRequest):
            reserve_parts_request(obj, user=request.user)
            _notify_new_parts_requests([obj])
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
    if request.user.profile == "warehouse" and module != "requests":
        return HttpResponseForbidden(_("Your profile can only manage warehouse inventory and parts requests."))
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
    original_parts_values = None
    if isinstance(obj, PartsRequest):
        if obj.status in ("delivered", "cancelled"):
            messages.error(request, _("Delivered or rejected requests cannot be edited."))
            return redirect("fleet:workflow_list", module=module)
        original_parts_values = (
            obj.customer_quoted_price,
            obj.repair_minutes,
            obj.part_id,
            obj.quantity_requested,
            obj.approval_status,
        )
    if model is WorkOrder:
        form = WorkOrderForm(request.POST or None, instance=obj, workshop=workshop)
    else:
        exclude = FORM_EXCLUDES[model]
        if isinstance(obj, PartsRequest) and not _can_approve_parts(request.user):
            exclude = exclude + ("customer_quoted_price", "repair_minutes")
        Form = modelform_factory(model, exclude=exclude)
        form = Form(request.POST or None, request.FILES or None, instance=obj)
    for field in form.fields.values():
        if hasattr(field, "queryset"):
            related_model = field.queryset.model
            if hasattr(related_model, "workshop"):
                field.queryset = field.queryset.filter(workshop=workshop)
                if related_model is LaborArticle:
                    field.queryset = field.queryset.filter(is_active=True)
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
        changed_fields = set(form.changed_data)
        obj = form.save(commit=False)
        approval_terms_changed = False
        if isinstance(obj, PartsRequest) and original_parts_values is not None:
            previous_quote, previous_minutes, previous_part_id, previous_quantity, previous_approval_status = original_parts_values
            if "customer_quoted_price" not in changed_fields and (
                "part" in changed_fields or "quantity_requested" in changed_fields
            ):
                obj.customer_quoted_price = _parts_request_quote(
                    obj.part, obj.quantity_requested, obj.work_order.customer
                )
            approval_terms_changed = (
                obj.customer_quoted_price != previous_quote
                or obj.repair_minutes != previous_minutes
                or obj.part_id != previous_part_id
                or obj.quantity_requested != previous_quantity
            )
            if approval_terms_changed:
                approval_required = (
                    previous_approval_status != "not_required"
                    or (
                        obj.customer_quoted_price is not None
                        and obj.customer_quoted_price > CUSTOMER_APPROVAL_THRESHOLD
                    )
                )
                obj.approval_status = "awaiting_customer" if approval_required else "not_required"
                obj.customer_approval_recorded_at = None
                obj.customer_approval_recorded_by = None
                obj.approval_decided_at = None
                obj.approval_decided_by = None
                obj.status = "pending"
        if isinstance(obj, PartsRequest) and obj.supplier_offer_id:
            obj.supplier = str(obj.supplier_offer.supplier)
            obj.purchase_price = obj.supplier_offer.net_purchase_price
        with transaction.atomic():
            obj.save()
            form.save_m2m()
            if approval_terms_changed and obj.approval_status == "awaiting_customer":
                body = (
                    f"{obj.work_order.ro_number} · {obj.part or obj.custom_item} · "
                    f"{obj.customer_quoted_price} {workshop.currency} · {obj.repair_minutes} min"
                )
                _notify_profile(
                    workshop,
                    "admin",
                    _("Customer approval required"),
                    body,
                    "/richieste-ricambi/",
                    obj.work_order,
                )
                _notify_requester(obj, _("Request terms updated"), body)
        if isinstance(obj, Attachment) and "file" in request.FILES:
            obj.file_name = obj.file.name
            obj.save(update_fields=("file_name",))
        _audit(workshop, request.user, "update", model, obj)
        messages.success(request, _("%(title)s: changes saved.") % {"title": title})
        return redirect("fleet:workflow_list", module=module)
    return render(request, "fleet/workflow_form.html", {"form": form, "title": f"Modifica · {title}", "module": module})


def _next_job_number(work_order):
    latest = Job.objects.filter(work_order=work_order).aggregate(number=models.Max("job_number"))["number"]
    return (latest or 0) + 1


@login_required
def mechanic_open_job(request, order_pk):
    if not _is_mechanic(request.user):
        return HttpResponseForbidden(_("Only mechanics can open their own activities."))
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    title = request.POST.get("title", "").strip()
    if not title:
        messages.error(request, _("Enter an activity description."))
        return redirect("work_order_detail", pk=order_pk)

    try:
        with transaction.atomic():
            order = get_object_or_404(
                WorkOrder.objects.select_for_update(),
                pk=order_pk,
                workshop=workshop,
            )
            if order.status not in ("open", "in_progress"):
                raise ValidationError(_("This work order is no longer open."))
            if order.jobs.exists():
                raise ValidationError(_("This work order already has an activity."))
            job = Job.objects.create(
                workshop=workshop,
                work_order=order,
                job_number=_next_job_number(order),
                title=title,
                description=request.POST.get("description", "").strip(),
                department="technician",
                specialty="general",
            )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return redirect("work_order_detail", pk=order_pk)

    logger.info(
        "Meccanico ha aperto una nuova attività",
        extra={"work_order_id": order.pk, "activity_id": job.pk, "user_id": request.user.pk},
    )
    messages.success(request, _("Activity created. Start it to record working time."))
    return redirect(f"{reverse('work_order_detail', args=(order_pk,))}#job-{job.pk}")


@login_required
@transaction.atomic
def job_action(request, pk, action):
    if request.user.profile == "warehouse":
        return HttpResponseForbidden(_("Warehouse profiles cannot manage repair sessions."))
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    if request.method != "POST": return redirect("jobs")
    job = get_object_or_404(
        Job.objects.select_for_update().select_related("work_order"),
        pk=pk,
        workshop=workshop,
    )
    now = timezone.now()
    is_supervisor = request.user.is_administrator
    participation = JobParticipation.objects.select_for_update().filter(
        job=job, mechanic=request.user, is_active=True,
    ).first()

    if action == "call":
        if request.user.profile != "admin" and not request.user.is_superuser: return HttpResponseForbidden(_("Only an administrator can call a technician."))
        mechanic = get_object_or_404(request.user.__class__, pk=request.POST.get("mechanic"), profile="mechanic", is_active=True, memberships__workshop=workshop, memberships__is_active=True)
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
        logger.info(
            "Transizione attività registrata",
            extra={"work_order_id": job.work_order_id, "activity_id": job.pk, "user_id": request.user.pk, "transition": event_type or "call_accepted"},
        )
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
            logger.info(
                "Transizione attività registrata",
                extra={"work_order_id": job.work_order_id, "activity_id": job.pk, "user_id": request.user.pk, "transition": "reopen"},
            )
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
        reason_id = request.POST.get("pause_reason")
        reason = PauseReason.objects.filter(pk=reason_id, is_active=True).first() if reason_id else None
        if reason is None:
            messages.error(request, _("Select a pause reason before pausing."))
            return redirect("my_jobs" if _is_mechanic(request.user) else "jobs")
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
    elif action == "complete":
        return redirect("job_complete", pk=job.pk)
    else:
        messages.error(request, _("This action is not valid for your job session status."))
    _audit(workshop, request.user, action, Job, job)
    logger.info(
        "Transizione attività registrata",
        extra={"work_order_id": job.work_order_id, "activity_id": job.pk, "user_id": request.user.pk, "transition": action},
    )
    return redirect("my_jobs" if _is_mechanic(request.user) else "jobs")


@login_required
def my_jobs(request):
    if request.user.profile == "warehouse":
        return HttpResponseForbidden(_("Warehouse profiles cannot access repair sessions."))
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    return _render_my_jobs(request, workshop)


def _render_my_jobs(request, workshop, bound_request_formsets=None):
    bound_request_formsets = bound_request_formsets or {}
    calls = JobCall.objects.filter(workshop=workshop, mechanic=request.user, accepted_at__isnull=True,
        dismissed_at__isnull=True).select_related("job", "job__work_order", "called_by")
    participations = list(JobParticipation.objects.filter(workshop=workshop, mechanic=request.user,
        is_active=True).select_related("job", "job__work_order").prefetch_related(
            "job__parts_requests__part", "job__parts_used__part"
        ))
    for participation in participations:
        participation.pause_reason = None
        if participation.paused_at:
            latest_pause = TimeEvent.objects.filter(
                workshop=workshop,
                job=participation.job,
                mechanic=request.user,
                event_type="pause",
            ).select_related("pause_reason").order_by("-event_at", "-pk").first()
            participation.pause_reason = latest_pause.pause_reason if latest_pause else None
        participation.parts_formset = bound_request_formsets.get(participation.job_id) or PartsRequestFormSet(
            prefix=f"parts-{participation.job_id}", form_kwargs={"workshop": workshop}
        )
    recent_sessions = JobParticipation.objects.filter(
        workshop=workshop,
        mechanic=request.user,
        is_active=False,
        finished_at__isnull=False,
    ).select_related("job", "job__work_order").order_by("-finished_at")[:5]
    return render(request, "fleet/my_jobs.html", {
        "calls": calls,
        "participations": participations,
        "recent_sessions": recent_sessions,
        "pause_reasons": PauseReason.objects.filter(is_active=True),
    })


@login_required
def job_parts_request(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    job = get_object_or_404(
        Job.objects.select_related("work_order").prefetch_related(
            "parts_requests__part", "parts_used__part"
        ),
        pk=pk,
        workshop=workshop,
    )
    if not JobParticipation.objects.filter(
        workshop=workshop, job=job, mechanic=request.user, is_active=True
    ).exists():
        return HttpResponseForbidden(_("Only a technician with an active session can request parts for this job."))

    prefix = f"parts-{job.pk}"
    formset = PartsRequestFormSet(request.POST, prefix=prefix, form_kwargs={"workshop": workshop})
    if not formset.is_valid():
        return _render_my_jobs(request, workshop, {job.pk: formset})

    requests = []
    with transaction.atomic():
        for form in formset:
            data = form.cleaned_data
            if not data or data.get("DELETE") or not (data.get("part") or data.get("custom_item")):
                continue
            part = data["part"]
            item = PartsRequest(
                workshop=workshop,
                work_order=job.work_order,
                job=job,
                part=part,
                quantity_requested=data["quantity_requested"],
                unit=part.unit,
                notes=data.get("notes", "").strip(),
                requested_by=request.user,
            )
            _set_initial_parts_request_status(item)
            item.save()
            reserve_parts_request(item, user=request.user)
            requests.append(item)
            _audit(workshop, request.user, "create", PartsRequest, item)

        _notify_new_parts_requests(requests)

    messages.success(request, _("Parts request sent to the warehouse."))
    return redirect("my_jobs")


@login_required
def job_complete(request, pk):
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    job = get_object_or_404(
        Job.objects.select_related("work_order").prefetch_related(
            "parts_requests__part", "parts_used__part"
        ),
        pk=pk,
        workshop=workshop,
    )
    participation = JobParticipation.objects.filter(
        workshop=workshop, job=job, mechanic=request.user, is_active=True
    ).first()
    if participation is None:
        return HttpResponseForbidden(_("Only a technician with an active session can finish this job session."))

    prefix = f"used-parts-{job.pk}"
    formset = PartsUsageFormSet(
        request.POST or None, prefix=prefix, form_kwargs={"workshop": workshop}
    )
    confirmation_error = False
    stock_error = ""
    if request.method == "POST":
        if formset.is_valid() and request.POST.get("parts_used_confirmed") == "1":
            usages = [
                form.cleaned_data
                for form in formset
                if form.cleaned_data and not form.cleaned_data.get("DELETE") and form.cleaned_data.get("part")
            ]
            quantities_by_part = {}
            for usage in usages:
                part_id = usage["part"].pk
                quantities_by_part[part_id] = quantities_by_part.get(part_id, Decimal("0")) + usage["quantity_used"]

            with transaction.atomic():
                locked_job = get_object_or_404(
                    Job.objects.select_for_update().select_related("work_order"),
                    pk=job.pk, workshop=workshop,
                )
                locked_participation = JobParticipation.objects.select_for_update().filter(
                    workshop=workshop, job=locked_job, mechanic=request.user, is_active=True
                ).first()
                if locked_participation is None:
                    return HttpResponseForbidden(_("This job session is no longer active."))

                locked_parts = {
                    part.pk: part
                    for part in Part.objects.select_for_update().filter(
                        workshop=workshop, pk__in=quantities_by_part
                    )
                }
                missing_part_ids = quantities_by_part.keys() - locked_parts.keys()
                if missing_part_ids:
                    stock_error = _("A selected part is no longer available. Reload the page and try again.")
                elif quantities_by_part:
                    try:
                        reserve_job_usage(locked_job, quantities_by_part, user=request.user)
                    except InsufficientStockError as error:
                        stock_error = _("Insufficient unreserved stock for: %(parts)s.") % {
                            "parts": str(error)
                        }
                if not missing_part_ids and not stock_error:
                    now = timezone.now()
                    locked_participation.is_active = False
                    locked_participation.finished_at = now
                    locked_participation.paused_at = None
                    locked_participation.save(update_fields=("is_active", "finished_at", "paused_at"))
                    TimeEvent.objects.create(
                        workshop=workshop, job=locked_job, mechanic=request.user,
                        event_type="finish", event_at=now,
                    )
                    if not JobParticipation.objects.filter(job=locked_job, is_active=True).exists():
                        locked_job.status, locked_job.completed_at = "completed", now
                        locked_job.save(update_fields=("status", "completed_at", "updated_at"))
                    elif not JobParticipation.objects.filter(
                        job=locked_job, is_active=True, paused_at__isnull=True
                    ).exists():
                        locked_job.status = "paused"
                        locked_job.save(update_fields=("status", "updated_at"))
                    _audit(workshop, request.user, "complete", Job, locked_job)
                    messages.success(request, _("Session finished and the parts were reserved on the transfer slip."))
                    return redirect("my_jobs" if _is_mechanic(request.user) else "jobs")
        else:
            confirmation_error = request.POST.get("parts_used_confirmed") != "1"

    other_participations = JobParticipation.objects.filter(
        job=job, is_active=True
    ).exclude(mechanic=request.user).select_related("mechanic")
    return render(request, "fleet/job_complete.html", {
        "job": job,
        "formset": formset,
        "confirmation_error": confirmation_error,
        "stock_error": stock_error,
        "other_participations": other_participations,
    })


@login_required
def parts_request_action(request, pk, action):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")

    warehouse_actions = {"prepare", "hold", "resume", "ready", "deliver", "estimate", "order"}
    approval_actions = {"customer_approved", "customer_rejected", "approve", "reject"}
    if action == "remind" and not _is_mechanic(request.user):
        return HttpResponseForbidden(_("Only mechanics can remind the warehouse."))
    can_manage_supplier_orders = request.user.has_perm("parts.manage_supplier_purchasing")
    if action in warehouse_actions and not _can_manage_parts(request.user) and not (
        action == "order" and can_manage_supplier_orders
    ):
        return HttpResponseForbidden(_("Only warehouse staff can update warehouse requests."))
    if action in approval_actions and not _can_approve_parts(request.user):
        return HttpResponseForbidden(_("Only reception can update customer approvals."))
    if action not in warehouse_actions | approval_actions | {"remind"}:
        raise Http404

    with transaction.atomic():
        item = get_object_or_404(
            PartsRequest.objects.select_for_update(of=("self",)).select_related(
                "part", "requested_by", "work_order"
            ),
            pk=pk,
            workshop=workshop,
        )
        if action in warehouse_actions:
            if item.approval_status not in ("not_required", "approved"):
                messages.error(request, _("Customer approval must be completed before warehouse processing."))
                return redirect("fleet:workflow_list", module="requests")
            if action == "estimate" and item.status not in ("new", "pending", "preparing", "on_hold"):
                messages.error(request, _("A delivery estimate cannot be recorded for this request status."))
                return redirect("fleet:workflow_list", module="requests")
            if action == "estimate":
                eta_kind = request.POST.get("eta_kind", "")
                try:
                    eta_value = int(request.POST.get("eta_value", ""))
                except (TypeError, ValueError):
                    eta_value = 0
                if eta_kind not in ("stock", "supplier") or not 1 <= eta_value <= 100000:
                    messages.error(request, _("Enter a positive delivery estimate."))
                    return redirect("fleet:workflow_list", module="requests")
                now = timezone.now()
                item.warehouse_eta_kind = eta_kind
                item.warehouse_eta_value = eta_value
                item.warehouse_eta_updated_at = now
                item.warehouse_eta_updated_by = request.user
                item.warehouse_reminder_answered_at = now
                item.save(update_fields=(
                    "warehouse_eta_kind", "warehouse_eta_value", "warehouse_eta_updated_at",
                    "warehouse_eta_updated_by", "warehouse_reminder_answered_at", "updated_at",
                ))
                unit = _("minutes") if eta_kind == "stock" else _("days")
                _audit(workshop, request.user, "warehouse_estimate", PartsRequest, item,
                       details=f"{eta_value} {unit}")
                _notify_requester(
                    item,
                    _("Warehouse delivery estimate"),
                    _("%(item)s · Estimated delivery: %(value)s %(unit)s") % {
                        "item": item.part or item.custom_item,
                        "value": eta_value,
                        "unit": unit,
                    },
                )
                if eta_kind == "supplier":
                    _create_warehouse_note(
                        item,
                        request.user,
                        f"{item.part or item.custom_item}: ricambio non disponibile; "
                        f"consegna prevista entro {eta_value} giorni.",
                        timezone.localdate() + timedelta(days=eta_value),
                    )
                messages.success(request, _("Delivery estimate sent to the mechanic."))
            elif action == "prepare" and item.status in ("new", "pending"):
                item.status = "preparing"
                item.save(update_fields=("status", "updated_at"))
                _audit(workshop, request.user, "prepare", PartsRequest, item)
            elif action == "hold" and item.status in ("new", "pending", "preparing"):
                item.status = "on_hold"
                item.save(update_fields=("status", "updated_at"))
                _audit(workshop, request.user, "hold", PartsRequest, item)
                _create_warehouse_note(
                    item,
                    request.user,
                    f"{item.part or item.custom_item}: ricambio non disponibile in magazzino.",
                )
                _notify_requester(
                    item,
                    _("Part request on hold"),
                    f"{item.work_order.ro_number} · {item.part or item.custom_item} · "
                    f"{_('The warehouse does not currently have this part.')}",
                )
            elif action == "order" and item.status in ("new", "pending", "preparing", "on_hold"):
                try:
                    purchase_order = add_request_to_purchase_order(item, user=request.user)
                except ValidationError as error:
                    messages.error(request, " ".join(error.messages))
                    return redirect("fleet:workflow_list", module="requests")
                item.refresh_from_db()
                offer = item.supplier_offer
                lead_time = offer.lead_time_days if offer else None
                now = timezone.now()
                item.status = "on_hold"
                item.warehouse_eta_kind = "supplier"
                item.warehouse_eta_value = lead_time
                item.warehouse_eta_updated_at = now
                item.warehouse_eta_updated_by = request.user
                item.warehouse_reminder_answered_at = now
                item.save(update_fields=(
                    "status", "warehouse_eta_kind", "warehouse_eta_value", "warehouse_eta_updated_at",
                    "warehouse_eta_updated_by", "warehouse_reminder_answered_at", "updated_at",
                ))
                eta = timezone.localdate() + timedelta(days=lead_time) if lead_time else None
                eta_text = f" Consegna prevista il {eta:%d/%m/%Y}." if eta else ""
                _create_warehouse_note(
                    item,
                    request.user,
                    f"{item.part or item.custom_item}: ordinato al fornitore "
                    f"{item.supplier} con ordine {purchase_order.order_number}.{eta_text}",
                    eta,
                )
                _audit(
                    workshop, request.user, "supplier_order", PartsRequest, item,
                    details=purchase_order.order_number,
                )
                _notify_requester(
                    item,
                    _("Part ordered from supplier"),
                    f"{item.work_order.ro_number} · {item.part or item.custom_item} · "
                    f"{purchase_order.order_number}{eta_text}",
                )
                messages.success(request, _("The part was added to the supplier order."))
            elif action == "resume" and item.status == "on_hold":
                item.status = "pending"
                item.save(update_fields=("status", "updated_at"))
                _audit(workshop, request.user, "resume", PartsRequest, item)
                _notify_requester(
                    item,
                    _("Part request resumed"),
                    f"{item.work_order.ro_number} · {item.part or item.custom_item}",
                )
            elif action == "ready" and item.status == "preparing":
                if item.part_id:
                    line = reserve_parts_request(item, user=request.user)
                    required = item.quantity_requested * item.conversion_factor
                    if line is None or line.quantity_reserved < required:
                        messages.error(request, _("Insufficient unreserved stock: the request remains open."))
                        return redirect("fleet:workflow_list", module="requests")
                item.status = "ready_for_pickup"
                item.save(update_fields=("status", "updated_at"))
                _audit(workshop, request.user, "ready", PartsRequest, item)
                _notify_requester(
                    item,
                    _("Parts ready for pickup"),
                    f"{item.work_order.ro_number} · {item.part or item.custom_item}",
                )
            elif action == "deliver" and item.status == "ready_for_pickup":
                qty = item.quantity_delivered or item.quantity_requested
                if item.part_id and not item.inventory_applied:
                    line = TransferSlipLine.objects.select_for_update(of=("self",)).filter(
                        parts_request=item,
                    ).first()
                    if line is None or line.quantity_reserved < qty * item.conversion_factor:
                        messages.error(request, _("The requested quantity is not fully reserved."))
                        return redirect("fleet:workflow_list", module="requests")
                item.inventory_applied = True
                item.quantity_delivered = qty
                item.unit_delivered = item.unit
                item.status, item.delivered_at, item.delivered_by = "delivered", timezone.now(), request.user
                item.save()
                _audit(workshop, request.user, "deliver", PartsRequest, item)
                _notify_requester(
                    item,
                    _("Parts delivered"),
                    f"{item.work_order.ro_number} · {item.part or item.custom_item}",
                )
            else:
                messages.error(request, _("This warehouse action is not valid for the current request status."))
                return redirect("fleet:workflow_list", module="requests")
        elif action == "remind":
            if not item.job_id or not JobParticipation.objects.filter(
                workshop=workshop, job_id=item.job_id, mechanic=request.user, is_active=True
            ).exists():
                return HttpResponseForbidden(_("You can only remind the warehouse about parts for your active jobs."))
            if item.status not in ("new", "pending", "preparing", "on_hold") or item.approval_status not in ("not_required", "approved"):
                messages.error(request, _("This parts request cannot be sent to the warehouse in its current state."))
            elif item.warehouse_reminder_pending:
                messages.info(request, _("A warehouse reminder is already waiting for a reply."))
            else:
                item.warehouse_reminder_sent_at = timezone.now()
                item.save(update_fields=("warehouse_reminder_sent_at", "updated_at"))
                _audit(workshop, request.user, "warehouse_reminder", PartsRequest, item)
                _notify_profile(
                    workshop,
                    "warehouse",
                    _("Warehouse reminder"),
                    _("%(order)s · %(item)s · requested quantity: %(quantity)s %(unit)s") % {
                        "order": item.work_order.ro_number,
                        "item": item.part or item.custom_item,
                        "quantity": item.quantity_requested,
                        "unit": item.unit,
                    },
                    "/richieste-ricambi/",
                    item.work_order,
                )
                messages.success(request, _("Warehouse reminder sent."))
        elif action == "customer_approved" and item.approval_status == "awaiting_customer":
            item.approval_status = "pending"
            item.customer_approval_recorded_at = timezone.now()
            item.customer_approval_recorded_by = request.user
            item.save(update_fields=(
                "approval_status", "customer_approval_recorded_at",
                "customer_approval_recorded_by", "updated_at",
            ))
            _audit(workshop, request.user, "customer_approved", PartsRequest, item)
            _notify_profile(
                workshop,
                "admin",
                _("Customer approval recorded"),
                f"{item.work_order.ro_number} · {item.part or item.custom_item}",
                "/richieste-ricambi/",
                item.work_order,
            )
        elif action == "customer_rejected" and item.approval_status == "awaiting_customer":
            item.approval_status = "rejected"
            item.status = "cancelled"
            item.approval_decided_at = timezone.now()
            item.approval_decided_by = request.user
            item.save(update_fields=(
                "approval_status", "status", "approval_decided_at",
                "approval_decided_by", "updated_at",
            ))
            _audit(workshop, request.user, "customer_rejected", PartsRequest, item)
            _notify_requester(
                item,
                _("Customer declined the part request"),
                f"{item.work_order.ro_number} · {item.part or item.custom_item}",
            )
        elif action == "approve" and item.approval_status == "pending":
            item.approval_status = "approved"
            item.status = "pending"
            item.approval_decided_at = timezone.now()
            item.approval_decided_by = request.user
            item.save(update_fields=(
                "approval_status", "status", "approval_decided_at",
                "approval_decided_by", "updated_at",
            ))
            _audit(workshop, request.user, "approve", PartsRequest, item)
            _notify_profile(
                workshop,
                "warehouse",
                _("Approved request ready for warehouse"),
                f"{item.work_order.ro_number} · {item.part or item.custom_item}",
                "/richieste-ricambi/",
                item.work_order,
            )
            _notify_requester(
                item,
                _("Part request approved"),
                f"{item.work_order.ro_number} · {item.part or item.custom_item}",
            )
        elif action == "reject" and item.approval_status == "pending":
            item.approval_status = "rejected"
            item.status = "cancelled"
            item.approval_decided_at = timezone.now()
            item.approval_decided_by = request.user
            item.save(update_fields=(
                "approval_status", "status", "approval_decided_at",
                "approval_decided_by", "updated_at",
            ))
            _audit(workshop, request.user, "reject", PartsRequest, item)
            _notify_requester(
                item,
                _("Part request rejected"),
                f"{item.work_order.ro_number} · {item.part or item.custom_item}",
            )
        else:
            messages.error(request, _("This approval action is not valid for the current request status."))
            return redirect("fleet:workflow_list", module="requests")

    if action == "remind":
        return redirect("my_jobs")
    return redirect("fleet:workflow_list", module="requests")


@login_required
def workflow_status_action(request, module, pk):
    if request.user.profile == "warehouse":
        return HttpResponseForbidden(_("Warehouse profiles cannot update work order statuses."))
    if module not in ("orders", "requests") and _forbidden_for_mechanic(request):
        return _forbidden_for_mechanic(request)
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    if module == "requests":
        return HttpResponseForbidden(_("Use the warehouse and approval actions to change a parts request."))
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
    if isinstance(obj, WorkOrder):
        try:
            with transaction.atomic():
                obj = WorkOrder.objects.select_for_update().get(pk=pk, workshop=workshop)
                unfinished_jobs = obj.jobs.exclude(status__in=("completed", "cancelled"))
                if new_status == "ready_inspection" and (
                    not obj.jobs.exists() or unfinished_jobs.exists()
                ):
                    messages.error(request, _("Close every activity before advancing the work order."))
                    return redirect("fleet:workflow_list", module=module)
                if new_status == "completed" and unfinished_jobs.exists():
                    messages.error(request, _("The work order cannot be closed while activities are open."))
                    return redirect("fleet:workflow_list", module=module)
                if new_status == "completed":
                    close_transfer_slip(obj, user=request.user)
                    obj.completed_at = obj.completed_at or timezone.now()
                elif new_status == "cancelled":
                    cancel_transfer_slip(obj, user=request.user)
                obj.status = new_status
                obj.save(update_fields=("status", "completed_at", "updated_at"))
        except InsufficientStockError as error:
            messages.error(request, _("The work order cannot be closed because stock is unavailable: %(parts)s.") % {
                "parts": str(error),
            })
            return redirect("fleet:workflow_list", module=module)
        logger.info(
            "Stato ordine di lavoro aggiornato",
            extra={"work_order_id": obj.pk, "user_id": request.user.pk, "new_status": new_status},
        )
    else:
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
    if not isinstance(obj, WorkOrder):
        obj.save()
    _audit(workshop, request.user, "status", model, obj, new_status)
    return redirect("fleet:workflow_list", module=module)


@login_required
def work_order_billing(request, pk):
    if request.user.profile != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden(_("Billing prices are restricted to office staff."))
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    order = get_object_or_404(
        WorkOrder.objects.select_related("customer", "vehicle", "vehicle__owner"),
        pk=pk, workshop=workshop, status="completed",
    )
    effective_date = timezone.localtime(order.created_at).date()
    customer = order.customer or (order.vehicle.owner if order.vehicle_id else None)
    parts = order.parts_requests.filter(status="delivered").select_related("part").order_by("pk")
    jobs = order.jobs.filter(category="customer_pay").select_related("labor_article").order_by("pk")
    usages = JobPartUsage.objects.filter(job__work_order=order).select_related(
        "part", "job"
    ).order_by("pk")

    parts_formset = InvoicePartsRequestFormSet(
        request.POST if request.method == "POST" else None, queryset=parts, prefix="parts",
    )
    labor_formset = InvoiceLaborPriceFormSet(
        request.POST if request.method == "POST" else None, queryset=jobs, prefix="labor",
    )
    usage_formset = InvoiceUsagePriceFormSet(
        request.POST if request.method == "POST" else None, queryset=usages, prefix="usage",
    )
    forms_valid = request.method == "POST"
    if forms_valid:
        parts_valid = parts_formset.is_valid()
        labor_valid = labor_formset.is_valid()
        usage_valid = usage_formset.is_valid()
        forms_valid = parts_valid and labor_valid and usage_valid
    if forms_valid:
        with transaction.atomic():
            parts_formset.save()
            labor_formset.save()
            usage_formset.save()
            _audit(workshop, request.user, "billing_prices_updated", WorkOrder, order)
        messages.success(request, _("Billing prices were updated."))
        return redirect("work_order_billing", pk=order.pk)

    for form in parts_formset:
        item = form.instance
        quantity = item.quantity_delivered or item.quantity_requested
        proposed = (
            resolve_item_price(customer, part=item.part, effective_date=effective_date)["total_unit_price"]
            if item.part_id else None
        )
        form.proposed_price = proposed
        form.line_label = str(item.part) if item.part_id else item.custom_item
        form.quantity = quantity
        if not form.is_bound and item.invoice_unit_price_override is None and proposed is not None:
            form.initial["invoice_unit_price_override"] = proposed
    for form in labor_formset:
        job = form.instance
        proposed = (
            resolve_item_price(
                customer, labor_article=job.labor_article, effective_date=effective_date,
            )["total_unit_price"]
            if job.labor_article_id else None
        )
        form.proposed_price = proposed
        form.line_label = job.title
        form.quantity = Decimal(_job_minutes(job)) / Decimal(60)
        if not form.is_bound and job.invoice_hourly_rate_override is None and proposed is not None:
            form.initial["invoice_hourly_rate_override"] = proposed
    for form in usage_formset:
        usage = form.instance
        proposed = resolve_item_price(
            customer, part=usage.part, effective_date=effective_date,
        )["total_unit_price"]
        form.proposed_price = proposed
        form.line_label = f"{usage.part} · {usage.job.title}"
        form.quantity = usage.quantity_used
        if not form.is_bound and usage.invoice_unit_price_override is None and proposed is not None:
            form.initial["invoice_unit_price_override"] = proposed

    return render(request, "fleet/work_order_billing.html", {
        "order": order,
        "effective_date": effective_date,
        "parts_formset": parts_formset,
        "labor_formset": labor_formset,
        "item_page": item_page,
        "usage_formset": usage_formset,
    })


@login_required
def work_order_report(request, pk):
    if request.user.profile != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden(_("The billing report is restricted to office staff."))
    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")
    order = get_object_or_404(
        WorkOrder.objects.select_related("customer", "vehicle", "vehicle__owner"),
        pk=pk, workshop=workshop, status="completed",
    )
    effective_date = timezone.localtime(order.created_at).date()

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
        [labelled("Chiuso il", timezone.localtime(order.completed_at).strftime("%d/%m/%Y %H:%M") if order.completed_at else "—"), labelled("Tariffa manodopera", "Selezionata per ogni riga di lavorazione")],
        [labelled("Richiesta / diagnosi", order.reception_notes or "—"), labelled("", "")],
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

    jobs = list(order.jobs.select_related("labor_article").all())
    job_rows = [[paragraph("Intervento", "SmallCell"), paragraph("Tariffa", "SmallCell"), paragraph("Stato", "SmallCell"), paragraph("Ore", "RightCell"), paragraph("Importo", "RightCell")]]
    total_minutes = 0
    labor_total = Decimal("0.00")
    for job in jobs:
        minutes = _job_minutes(job)
        total_minutes += minutes
        article = job.labor_article if job.labor_article_id and job.category == "customer_pay" else None
        customer = order.customer or (order.vehicle.owner if order.vehicle_id else None)
        rate = job.invoice_hourly_rate_override if job.category == "customer_pay" else None
        if rate is None and article:
            rate = resolve_item_price(
                customer, labor_article=article, effective_date=effective_date,
            )["total_unit_price"]
        amount = (Decimal(minutes) / Decimal(60) * rate).quantize(Decimal("0.01")) if rate is not None else None
        if amount is not None:
            labor_total += amount
        tariff_label = "Prezzo personalizzato" if job.invoice_hourly_rate_override is not None else (
            article.get_tariff_type_display() if article else ""
        )
        tariff = f"{tariff_label} · {money(rate)}/h" if rate is not None else "—"
        job_rows.append([labelled(job.title, job.description or "", "SmallCell"),
                         paragraph(tariff, "SmallCell"),
                         paragraph(job.get_status_display(), "SmallCell"),
                         paragraph(f"{minutes / 60:.2f}", "RightCell"),
                         paragraph(money(amount) if amount is not None else ("Non addebitato" if job.category != "customer_pay" else "Prezzo da definire"), "RightCell")])
    if not jobs:
        job_rows.append([paragraph("Nessun lavoro registrato", "SmallCell"), paragraph("—", "SmallCell"), paragraph("—", "SmallCell"), paragraph("0,00", "RightCell"), paragraph("—", "RightCell")])
    job_table = LongTable(job_rows, colWidths=(60 * mm, 35 * mm, 25 * mm, 25 * mm, 27 * mm), repeatRows=1)
    job_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8F2")),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#C9D5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([job_table, Spacer(1, 3 * mm), paragraph(f"Tempo consuntivo totale: {total_minutes / 60:.2f} ore · Totale manodopera: {money(labor_total)}", "RightCell"), Spacer(1, 5 * mm), Paragraph("Ricambi utilizzati", styles["Heading2"])])

    requests = list(order.parts_requests.filter(status="delivered").select_related("part"))
    usages = list(JobPartUsage.objects.filter(job__work_order=order).select_related("part"))
    part_rows = [[paragraph("Articolo", "SmallCell"), paragraph("Quantità", "RightCell"), paragraph("Prezzo unitario", "RightCell"), paragraph("Importo", "RightCell")]]
    parts_total = 0
    for item in requests:
        quantity = item.quantity_delivered or item.quantity_requested
        name = str(item.part) if item.part_id else item.custom_item
        customer = order.customer or (order.vehicle.owner if order.vehicle_id else None)
        unit_price = item.invoice_unit_price_override
        if unit_price is None and item.part_id:
            unit_price = resolve_item_price(
                customer, part=item.part, effective_date=effective_date,
            )["total_unit_price"]
        line_total = quantity * unit_price if unit_price is not None else None
        if line_total is not None:
            parts_total += line_total
        part_rows.append([paragraph(name, "SmallCell"), paragraph(f"{quantity} {item.unit_delivered or item.unit}", "RightCell"),
                          paragraph(money(unit_price) if unit_price is not None else "Da definire", "RightCell"),
                          paragraph(money(line_total) if line_total is not None else "Da definire", "RightCell")])
    for usage in usages:
        customer = order.customer or (order.vehicle.owner if order.vehicle_id else None)
        unit_price = usage.invoice_unit_price_override
        if unit_price is None:
            unit_price = resolve_item_price(
                customer, part=usage.part, effective_date=effective_date,
            )["total_unit_price"]
        line_total = usage.quantity_used * unit_price if unit_price is not None else None
        if line_total is not None:
            parts_total += line_total
        part_rows.append([
            paragraph(f"{usage.part} · Consumo da magazzino", "SmallCell"),
            paragraph(f"{usage.quantity_used} {usage.part.unit}", "RightCell"),
            paragraph(money(unit_price) if unit_price is not None else "Da definire", "RightCell"),
            paragraph(money(line_total) if line_total is not None else "Da definire", "RightCell"),
        ])
    if not requests and not usages:
        part_rows.append([paragraph("Nessun ricambio registrato come consegnato", "SmallCell"), paragraph("—", "RightCell"), paragraph("—", "RightCell"), paragraph("—", "RightCell")])
    part_table = LongTable(part_rows, colWidths=(83 * mm, 29 * mm, 35 * mm, 25 * mm), repeatRows=1)
    part_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE8F2")),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#C9D5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    total = Table([[paragraph("Totale ricambi", "RightCell"), paragraph(money(parts_total), "RightCell")],
                   [paragraph("Totale manodopera", "RightCell"), paragraph(money(labor_total), "RightCell")],
                   [paragraph("Totale imponibile stimato", "RightCell"), paragraph(money(parts_total + labor_total), "RightCell")]], colWidths=(141 * mm, 31 * mm), hAlign="RIGHT")
    total.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), .8, colors.HexColor("#12263D")), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    story.extend([part_table, Spacer(1, 2 * mm), total, Spacer(1, 8 * mm),
                  paragraph("Prezzi validi alla data di apertura dell'OdL, salvo override salvati sulle singole righe. Documento riepilogativo non fiscale.", "SmallCell")])
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
    if request.user.profile != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden(_("Reports are available to administrators."))
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return redirect("home")

    today = timezone.localdate()
    initial = {"date_from": today.replace(day=1), "date_to": today}
    filters = request.GET.copy()
    if request.GET:
        filters.setdefault("date_from", initial["date_from"].isoformat())
        filters.setdefault("date_to", initial["date_to"].isoformat())
    form = TimeReportFilterForm(
        filters if request.GET else None,
        initial=initial,
        workshop=workshop,
    )
    if not form.is_valid():
        if request.GET.get("export"):
            return HttpResponseBadRequest(_("Correct the report filters before exporting."))
        return render(request, "fleet/report.html", {
            "form": form,
            "report_data": None,
            "period_start": initial["date_from"],
            "period_end": initial["date_to"],
        })

    date_from = form.cleaned_data["date_from"]
    date_to = form.cleaned_data["date_to"]
    period_start = timezone.make_aware(datetime.combine(date_from, time.min))
    period_end = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min))
    technician = form.cleaned_data["technician"]
    report_data = build_time_report(workshop, period_start, period_end, technician)
    export_format = request.GET.get("export", "")
    if export_format == "pdf":
        content = export_time_report_pdf(report_data, date_from, date_to, technician)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="consuntivo-{date_from:%Y%m%d}-{date_to:%Y%m%d}.pdf"'
        )
        return response
    if export_format in ("xlsx", "excel"):
        content = export_time_report_excel(report_data, date_from, date_to, technician)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="consuntivo-{date_from:%Y%m%d}-{date_to:%Y%m%d}.xlsx"'
        )
        return response
    if export_format:
        return HttpResponseBadRequest(_("Unsupported report export format."))

    return render(request, "fleet/report.html", {
        "form": form,
        "report_data": report_data,
        "period_start": date_from,
        "period_end": date_to,
        "selected_technician": technician,
    })


@login_required
def notifications(request):
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    items = Notification.objects.filter(workshop=workshop).filter(models.Q(user=request.user) | models.Q(user__isnull=True))
    return render(request, "fleet/notifications.html", {"items": items})


@login_required
def notifications_feed(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    workshop = _workshop_or_redirect(request)
    if workshop is None:
        return JsonResponse({"error": "No active workshop."}, status=400)
    try:
        after_id = max(0, int(request.GET.get("after", "0")))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid notification cursor."}, status=400)

    visible = Notification.objects.filter(workshop=workshop).filter(
        models.Q(user=request.user) | models.Q(user__isnull=True)
    )
    latest_id = visible.order_by("-pk").values_list("pk", flat=True).first() or 0
    unread_count = visible.filter(read=False).count()
    new_items = list(
        visible.filter(read=False, pk__gt=after_id).order_by("pk")[:20]
    )
    cursor = new_items[-1].pk if len(new_items) == 20 else max(after_id, latest_id)
    return JsonResponse({
        "unread_count": unread_count,
        "cursor": cursor,
        "notifications": [
            {
                "id": item.pk,
                "title": item.title,
                "body": item.body,
                "link": item.link,
            }
            for item in new_items
        ],
    })


@login_required
def audit_log(request):
    if request.user.profile != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden(_("The activity log is available to administrators."))
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    return render(request, "fleet/audit_log.html", {"items": AuditLog.objects.filter(workshop=workshop).select_related("actor", "work_order")[:300]})


@login_required
def data_export(request):
    if request.user.profile != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden(_("Data export is available to administrators."))
    workshop = _workshop_or_redirect(request)
    if workshop is None: return redirect("home")
    models_to_export = (Workshop, Membership, CamperOwner, Camper, CamperPhoto, WorkOrder, Job, Quote, QuoteLine, Part, PartMovement,
                        PartSupplierOffer, PartDocument,
                        PartsRequest, JobPartUsage, WarrantyClaim, WarrantyReturn, JobNote,
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


def work_order_list(request):
    return workflow_list(request, "orders")


def work_order_create(request):
    return workflow_create(request, "orders")


def work_order_status(request, pk):
    return workflow_status_action(request, "orders", pk)


def job_list(request):
    return workflow_list(request, "jobs")


def job_create(request):
    return workflow_create(request, "jobs")


def _catalog_context(request):
    membership = Membership.objects.filter(user=request.user, is_active=True, workshop__is_active=True).select_related("workshop").first()
    return membership.workshop if membership else None


@login_required
def bom_list(request):
    if getattr(request.user, "profile", "") != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden("Solo gli amministratori possono gestire le distinte base.")
    workshop = _catalog_context(request)
    boms = BillOfMaterials.objects.filter(workshop=workshop).annotate(
        line_count=Count("lines")
    ) if workshop else BillOfMaterials.objects.none()
    search = request.GET.get("q", "").strip()
    if search:
        boms = boms.filter(
            models.Q(code__icontains=search)
            | models.Q(name__icontains=search)
            | models.Q(description__icontains=search)
        )
    page = Paginator(boms.order_by("name", "code"), 50).get_page(request.GET.get("page"))
    return render(request, "orders/bom_list.html", {
        "boms": page,
        "page_obj": page,
        "search": search,
        "has_workshop": workshop is not None,
    })


@login_required
def bom_form(request, pk=None):
    if getattr(request.user, "profile", "") != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden("Solo gli amministratori possono gestire le distinte base.")
    workshop = _catalog_context(request)
    if workshop is None:
        return redirect("home")
    bom = get_object_or_404(BillOfMaterials, pk=pk, workshop=workshop) if pk else BillOfMaterials(workshop=workshop)
    form = BillOfMaterialsForm(request.POST or None, instance=bom)
    line_formset = BillOfMaterialsLineFormSet(
        request.POST or None,
        instance=bom,
        form_kwargs={"workshop": workshop},
    )
    if request.method == "POST" and form.is_valid() and line_formset.is_valid():
        with transaction.atomic():
            bom = form.save(commit=False)
            bom.workshop = workshop
            bom.save()
            line_formset.instance = bom
            line_formset.save()
        messages.success(request, "Distinta base salvata.")
        return redirect("bom_edit", pk=bom.pk)
    return render(request, "orders/bom_form.html", {
        "form": form,
        "line_formset": line_formset,
        "bom": bom,
    })


@login_required
def price_list_list(request):
    if getattr(request.user, "profile", "") != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden("Solo il personale d'ufficio può gestire i listini.")
    workshop = _catalog_context(request)
    lists = (
        PriceList.objects.filter(workshop=workshop)
        .select_related("customer")
        .annotate(item_count=Count("items"))
        if workshop else PriceList.objects.none()
    )
    search = request.GET.get("q", "").strip()
    if search:
        lists = lists.filter(
            models.Q(code__icontains=search)
            | models.Q(name__icontains=search)
            | models.Q(customer__company_name__icontains=search)
            | models.Q(customer__first_name__icontains=search)
            | models.Q(customer__last_name__icontains=search)
        )
    kind = request.GET.get("tipo", "").strip()
    if kind == "cliente":
        lists = lists.filter(customer__isnull=False)
    elif kind == "generale":
        lists = lists.filter(customer__isnull=True)
    elif kind == "rotabile":
        lists = lists.filter(customer__isnull=True)
    lists = lists.order_by("-is_default", "-is_workshop", "name", "code")
    page = Paginator(lists, 50).get_page(request.GET.get("page"))
    return render(request, "orders/price_list_list.html", {
        "price_lists": page,
        "page_obj": page,
        "has_workshop": workshop is not None,
        "search": search,
        "kind": kind,
    })


@login_required
def price_list_rotate(request, pk):
    if getattr(request.user, "profile", "") != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden("Solo il personale d'ufficio può gestire i listini.")
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    workshop = _catalog_context(request)
    if workshop is None:
        return redirect("home")
    price_list = get_object_or_404(PriceList, pk=pk, workshop=workshop)
    try:
        rotated_count, skipped_count = rotate_price_list_prices(price_list)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(
            request,
            f"Prezzi ruotati per {rotated_count} articoli; "
            f"{skipped_count} mantenuti invariati perché privi di prezzo futuro.",
        )
    return redirect("price_list_edit", pk=price_list.pk)


@login_required
def price_list_add_item(request, pk):
    if getattr(request.user, "profile", "") != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden("Solo il personale d'ufficio può gestire i listini.")
    workshop = _catalog_context(request)
    if workshop is None:
        return redirect("home")
    price_list = get_object_or_404(PriceList, pk=pk, workshop=workshop)

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
            return redirect("price_list_add_item", pk=price_list.pk)
        current_raw = request.POST.get("current_price", "").strip().replace(",", ".")
        future_raw = request.POST.get("future_price", "").strip().replace(",", ".")
        if not current_raw:
            messages.error(request, "Il prezzo corrente è obbligatorio.")
            return redirect("price_list_add_item", pk=price_list.pk)
        try:
            current_price = Decimal(current_raw)
            future_price = Decimal(future_raw) if future_raw else None
        except Exception:
            messages.error(request, "Inserisci prezzi numerici validi.")
            return redirect("price_list_add_item", pk=price_list.pk)
        if current_price < 0 or (future_price is not None and future_price < 0):
            messages.error(request, "I prezzi non possono essere negativi.")
            return redirect("price_list_add_item", pk=price_list.pk)
        item, created = PriceListItem.objects.get_or_create(
            price_list=price_list,
            part=part,
            defaults={
                "unit_price": current_price,
                "valid_from": price_list.current_valid_from,
                "future_price": future_price,
                "future_valid_from": price_list.future_valid_from,
            },
        )
        if not created:
            messages.error(request, "Esiste già un prezzo per questo articolo nel listino.")
        else:
            messages.success(request, "Prezzo aggiunto al listino.")
        return redirect("price_list_grid", pk=price_list.pk)

    return render(request, "orders/price_list_add_item.html", {
        "price_list": price_list,
        "parts": page,
        "page_obj": page,
        "search": search,
    })


@login_required
def price_list_grid(request, pk):
    if getattr(request.user, "profile", "") != "admin" and not request.user.is_superuser:
        return HttpResponseForbidden("Solo il personale d'ufficio può gestire i listini.")
    workshop = _catalog_context(request)
    if workshop is None:
        return redirect("home")
    price_list = get_object_or_404(PriceList, pk=pk, workshop=workshop)

    if request.method == "POST":
        changed_count = 0
        with transaction.atomic():
            for key, value in request.POST.items():
                if not key.startswith("current_") and not key.startswith("future_"):
                    continue
                field, item_id = key.rsplit("_", 1)
                try:
                    part_id = int(item_id)
                except (TypeError, ValueError):
                    continue
                part = Part.objects.filter(pk=part_id, workshop=workshop).first()
                if part is None:
                    continue
                item, _ = PriceListItem.objects.get_or_create(
                    price_list=price_list,
                    part=part,
                    defaults={
                        "valid_from": price_list.current_valid_from,
                        "unit_price": Decimal("0"),
                    },
                )
                raw = value.strip().replace(",", ".")
                if not raw:
                    if field == "future":
                        item.future_price = None
                        item.future_valid_from = None
                        changed_count += 1
                        item.save(update_fields=("future_price", "future_valid_from"))
                    continue
                try:
                    price = Decimal(raw)
                except Exception:
                    continue
                if price is not None and price < 0:
                    continue
                if field == "current":
                    item.unit_price = price or Decimal("0")
                    item.valid_from = price_list.current_valid_from
                    changed_count += 1
                else:
                    item.future_price = price
                    item.future_valid_from = price_list.future_valid_from
                    changed_count += 1
                item.full_clean()
                item.save()
            if changed_count:
                messages.success(request, f"Aggiornate {changed_count} celle prezzo.")
        return redirect(f"{reverse('price_list_grid', args=(price_list.pk,))}?{request.META.get('QUERY_STRING', '')}")

    search = request.GET.get("q", "").strip()
    items = PriceListItem.objects.filter(
        price_list=price_list,
        part__isnull=False,
    ).select_related("part").order_by("part__part_number", "pk")
    if search:
        items = items.filter(
            models.Q(part__part_number__icontains=search)
            | models.Q(part__name__icontains=search)
            | models.Q(part__description__icontains=search)
        )
    page = Paginator(items, 50).get_page(request.GET.get("page"))
    rows = [
        {
            "part": item.part,
            "item": item,
        }
        for item in page.object_list
    ]
    return render(request, "orders/price_list_grid.html", {
        "price_list": price_list,
        "rows": rows,
        "page_obj": page,
        "search": search,
    })


@login_required
def price_list_form(request, pk=None):
    if getattr(request.user, "profile", "") != "admin" and not request.user.is_superuser:
        messages.error(request, "Solo il personale d'ufficio può gestire i listini.")
        return redirect("price_lists")
    workshop = _catalog_context(request)
    if workshop is None:
        return redirect("home")
    price_list = get_object_or_404(PriceList, pk=pk, workshop=workshop) if pk else PriceList(workshop=workshop)

    customer = price_list.customer if price_list.customer_id else None
    customer_page = None
    customer_search = ""
    if not pk:
        customer_search = request.GET.get("customer_q", "").strip()
        customer_queryset = CamperOwner.objects.filter(
            workshop=workshop,
            kind__in=("customer", "both"),
        )
        if customer_search:
            customer_queryset = customer_queryset.filter(
                models.Q(company_name__icontains=customer_search)
                | models.Q(first_name__icontains=customer_search)
                | models.Q(last_name__icontains=customer_search)
                | models.Q(email__icontains=customer_search)
            )
        customer_page = Paginator(
            customer_queryset.order_by("last_name", "first_name", "company_name", "pk"),
            50,
        ).get_page(request.GET.get("customer_page"))
    if not pk and request.GET.get("customer"):
        customer = get_object_or_404(
            CamperOwner, pk=request.GET["customer"], workshop=workshop, kind__in=("customer", "both")
        )
        existing_list = PriceList.objects.filter(workshop=workshop, customer=customer).first()
        if existing_list:
            return redirect("price_list_edit", pk=existing_list.pk)
        price_list.customer = customer
        price_list.code = customer.customer_code
        price_list.name = f"Listino {customer}"
    customer_from_contact = customer is not None

    allow_labor_creation = price_list.is_default
    form = PriceListForm(
        request.POST or None, instance=price_list, workshop=workshop, customer=customer,
    )
    form_valid = form.is_valid()
    if customer is None and form.is_bound:
        customer = form.cleaned_data.get("customer")
    is_customer_list = customer is not None
    valid = form_valid
    if request.method == "POST" and valid:
        price_list = form.save(commit=False)
        price_list.workshop = workshop
        try:
            price_list.full_clean()
        except ValidationError as error:
            form.add_error(None, error)
        else:
            with transaction.atomic():
                previous_customer_id = (
                    PriceList.objects.filter(pk=price_list.pk).values_list("customer_id", flat=True).first()
                    if price_list.pk else None
                )
                if customer is not None:
                    price_list.customer = customer
                    price_list.code = customer.customer_code
                    price_list.name = f"Listino {customer}"
                price_list.save()
                if price_list.is_default:
                    ensure_workshop_price_list(workshop)

                if previous_customer_id and previous_customer_id != price_list.customer_id:
                    previous_customer = CamperOwner.objects.select_for_update().get(pk=previous_customer_id)
                    if previous_customer.price_list_id == price_list.pk:
                        default_list = PriceList.objects.get(workshop=workshop, is_default=True)
                        previous_customer.price_list = default_list
                        previous_customer.save(update_fields=("price_list",))
                if price_list.customer_id:
                    assigned_customer = CamperOwner.objects.select_for_update().get(pk=price_list.customer_id)
                    assigned_customer.price_list = price_list
                    assigned_customer.save(update_fields=("price_list",))
            messages.success(request, "Listino salvato.")
            return redirect("customer_detail", pk=customer.pk) if customer_from_contact else redirect("price_lists")
    return render(request, "orders/price_list_form.html", {
        "form": form,
        "customer_page": customer_page,
        "customer_search": customer_search,
        "can_rotate": bool(price_list.pk and price_list.customer_id is None),
        "price_list": price_list if price_list.pk else None,
        "title": "Modifica listino" if price_list.pk else "Nuovo listino",
    })
