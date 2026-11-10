from django.contrib import admin

from .models import AuditLog


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
