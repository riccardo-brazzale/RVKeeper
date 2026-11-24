
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth import logout
from types import MethodType

from .models import AuthenticationSettings, User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from workshops.models import Membership


_admin_login = admin.site.login


def _always_fresh_admin_login(self, request, extra_context=None):
    if request.user.is_authenticated:
        logout(request)
    return _admin_login(request, extra_context)


admin.site.login = MethodType(_always_fresh_admin_login, admin.site)
admin.site.unregister(Group)


@admin.register(AuthenticationSettings)
class AuthenticationSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Sicurezza sessione", {
            "fields": ("idle_timeout_minutes", "session_duration_hours"),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect
        settings_object = AuthenticationSettings.get_solo()
        return redirect(
            "admin:accounts_authenticationsettings_change",
            settings_object.pk,
        )


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ("workshop", "is_active")


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    model = User

    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    inlines = (MembershipInline,)

    ordering = ("username",)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "preferred_language",
        "profile",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "preferred_language",
        "profile",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )

    fieldsets = (
        (None, {
            "fields": ("username", "email", "password")
        }),
        ("Informazioni personali", {
            "fields": (
                "first_name",
                "last_name",
                "preferred_language",
                "profile",
            )
        }),
        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
            )
        }),
        ("Important Dates", {
            "fields": (
                "last_login",
                "date_joined",
            )
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username",
                "email",
                "preferred_language",
                "profile",
                "password1",
                "password2",
                "is_active",
                "is_staff",
                "is_superuser",
            ),
        }),
    )

