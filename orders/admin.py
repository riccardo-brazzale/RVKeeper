from django.contrib import admin

from .models import (
    Attachment,
    AuditLog,
    DocumentCategory,
    JobAssignment,
    JobCall,
    JobNote,
    JobParticipation,
    Notification,
    PauseReason,
    TimeEvent,
    WarrantyClaim,
    WarrantyReturn,
)


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
