from django.contrib import admin

from .models import (
    Attachment,
    AuditLog,
    CustomerItemDiscount,
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
)


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("ro_number", "customer", "vehicle", "status", "work_classification", "invoiced", "created_at")
    list_filter = ("workshop", "status", "work_classification", "warranty_status", "invoiced")
    search_fields = ("ro_number", "customer_name", "customer__company_name", "vehicle__plate")
    date_hierarchy = "created_at"


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("work_order", "job_number", "title", "status", "category", "department", "parts_ready")
    list_filter = ("workshop", "status", "category", "department", "specialty")
    search_fields = ("title", "work_order__ro_number")


@admin.register(LaborArticle)
class LaborArticleAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "tariff_type", "workshop", "is_active")
    list_filter = ("workshop", "tariff_type", "is_active")
    search_fields = ("code", "description")


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "workshop", "customer", "is_default", "is_workshop", "is_active")
    list_filter = ("workshop", "is_default", "is_workshop", "is_active")
    search_fields = ("code", "name", "customer__company_name")


@admin.register(PriceListItem)
class PriceListItemAdmin(admin.ModelAdmin):
    list_display = ("price_list", "part", "labor_article", "article_class", "article_group", "unit_price", "valid_from")
    list_filter = ("price_list", "valid_from")
    search_fields = ("price_list__code", "part__part_number", "labor_article__code")


@admin.register(CustomerItemDiscount)
class CustomerItemDiscountAdmin(admin.ModelAdmin):
    list_display = ("customer", "part", "labor_article", "article_class", "article_group", "discount_percent")
    list_filter = ("customer",)
    search_fields = ("customer__company_name", "part__part_number", "labor_article__code")


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name", "code", "description")
    prepopulated_fields = {"code": ("name",)}


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("file_name", "category", "work_order", "job", "uploaded_by", "created_at")
    list_filter = ("category", "department", "created_at")
    search_fields = ("file_name", "caption", "work_order__ro_number")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "workshop", "actor", "action", "entity_type", "entity_id")
    list_filter = ("workshop", "action", "entity_type", "created_at")
    search_fields = ("actor__email", "action", "entity_type", "entity_id", "details")
    date_hierarchy = "created_at"
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PauseReason)
class PauseReasonAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"code": ("label",)}


@admin.register(JobCall)
class JobCallAdmin(admin.ModelAdmin):
    list_display = ("job", "mechanic", "called_by", "created_at", "accepted_at")
    list_filter = ("created_at", "accepted_at")
    search_fields = ("job__title", "mechanic__username")


@admin.register(JobAssignment)
class JobAssignmentAdmin(admin.ModelAdmin):
    list_display = ("job", "from_technician", "to_technician", "created_at")
    list_filter = ("workshop", "created_at")


@admin.register(JobNote)
class JobNoteAdmin(admin.ModelAdmin):
    list_display = ("job", "author", "department", "created_at")
    list_filter = ("workshop", "department", "created_at")
    search_fields = ("job__title", "text")


@admin.register(JobParticipation)
class JobParticipationAdmin(admin.ModelAdmin):
    list_display = ("job", "mechanic", "source", "is_active", "started_at", "finished_at")
    list_filter = ("workshop", "source", "is_active")
    search_fields = ("job__title", "mechanic__username")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "work_order", "read", "created_at")
    list_filter = ("workshop", "read", "created_at")
    search_fields = ("title", "body", "user__username")


@admin.register(TimeEvent)
class TimeEventAdmin(admin.ModelAdmin):
    list_display = ("job", "mechanic", "event_type", "event_at")
    list_filter = ("workshop", "event_type", "event_at")
    search_fields = ("job__title", "mechanic__username")


@admin.register(WarrantyClaim)
class WarrantyClaimAdmin(admin.ModelAdmin):
    list_display = ("work_order", "component", "status", "requested_by", "created_at")
    list_filter = ("workshop", "status", "created_at")
    search_fields = ("work_order__ro_number", "component", "problem_description")


@admin.register(WarrantyReturn)
class WarrantyReturnAdmin(admin.ModelAdmin):
    list_display = ("work_order", "part_name", "status", "requested_by", "created_at")
    list_filter = ("workshop", "status", "created_at")
    search_fields = ("work_order__ro_number", "part_name", "part_number")
