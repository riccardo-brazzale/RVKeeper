
from django.contrib import admin
from .models import Workshop, Membership


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "country",
        "default_language",
        "currency",
        "is_active",
    )
    search_fields = ("name", "slug")
    list_filter = ("country", "is_active")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workshop", "is_active")
    list_filter = ("workshop", "is_active")
    search_fields = ("user__email", "workshop__name")
