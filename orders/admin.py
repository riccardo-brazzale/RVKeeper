from django.contrib import admin

from .models import JobCall, PauseReason


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
