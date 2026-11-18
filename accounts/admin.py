
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from workshops.models import Membership


admin.site.unregister(Group)


class MembershipInline(admin.TabularInline):
    model = Membership
    verbose_name = _("Workshop membership")
    verbose_name_plural = _("Workshop memberships")
    extra = 0
    fields = ("workshop", "is_active")


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    model = User

    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    inlines = (MembershipInline,)

    def save_model(self, request, obj, form, change):
        # The profile determines access to the administration site.
        obj.is_staff = obj.profile == "admin" or obj.is_superuser
        super().save_model(request, obj, form, change)

    ordering = ("username",)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "preferred_language",
        "profile",
        "is_active",
    )

    list_filter = (
        "is_active",
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
        (_("Personal details and profile"), {
            "fields": (
                "first_name",
                "last_name",
                "preferred_language",
                "profile",
            )
        }),
        (_("Access"), {
            "fields": (
                "is_active",
                "is_superuser",
            )
        }),
        (_("Dates"), {
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
                "is_superuser",
            ),
        }),
    )

