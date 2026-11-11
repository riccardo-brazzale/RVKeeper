
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from workshops.models import Membership


admin.site.unregister(Group)


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ("workshop", "role", "is_active")


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
        "seniority",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "preferred_language",
        "seniority",
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
                "department",
                "specialty",
                "seniority",
            )
        }),
        ("Permessi", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
            )
        }),
        ("Date importanti", {
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
                "password1",
                "password2",
                "is_active",
                "is_staff",
                "is_superuser",
            ),
        }),
    )

