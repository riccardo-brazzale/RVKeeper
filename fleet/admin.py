from django.contrib import admin

from .models import Attachment, AuditLog, Camper, CamperPhoto, DocumentCategory


@admin.register(Camper)
class CamperAdmin(admin.ModelAdmin):
    list_display = ("internal_number", "plate", "brand", "model", "owner", "workshop", "is_active")
    list_filter = ("workshop", "is_active", "fuel_type", "transmission")
    search_fields = ("internal_number", "plate", "vin", "brand", "model", "owner__company_name", "owner__last_name")


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name", "code", "description")
    prepopulated_fields = {"code": ("name",)}


@admin.register(CamperPhoto)
class CamperPhotoAdmin(admin.ModelAdmin):
    list_display = ("camper", "category", "caption", "uploaded_at")
    list_filter = ("category", "uploaded_at")
    search_fields = ("camper__plate", "camper__internal_number", "caption")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("file_name", "category", "work_order", "job", "uploaded_by", "created_at")
    list_filter = ("category", "department", "created_at")
    search_fields = ("file_name", "caption", "work_order__ro_number")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "workshop",
        "actor",
        "action",
        "entity_type",
        "entity_id",
    )
    list_filter = ("workshop", "action", "entity_type", "created_at")
    search_fields = (
        "actor__email",
        "action",
        "entity_type",
        "entity_id",
        "details",
    )
    date_hierarchy = "created_at"
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
