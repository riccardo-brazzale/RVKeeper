
from django.contrib import admin
from .models import Workshop, Role, Membership


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


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "workshop",
        "is_system",
    )
    list_filter = ("workshop", "is_system")
    search_fields = ("name", "code")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workshop", "role", "is_active")
    list_filter = ("workshop", "role", "is_active")
    search_fields = ("user__email", "workshop__name")
