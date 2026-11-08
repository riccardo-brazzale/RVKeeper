
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    model = User

    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    ordering = ("email",)
    list_display = (
        "email",
        "first_name",
        "last_name",
        "preferred_language",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "preferred_language",
    )

    search_fields = (
        "email",
        "first_name",
        "last_name",
    )

    fieldsets = (
        (None, {
            "fields": ("email", "password")
        }),
        ("Informazioni personali", {
            "fields": (
                "first_name",
                "last_name",
                "preferred_language",
            )
        }),
        ("Permessi", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
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
                "email",
                "password1",
                "password2",
                "is_active",
                "is_staff",
                "is_superuser",
            ),
        }),
    )

    filter_horizontal = (
        "groups",
        "user_permissions",
    )
