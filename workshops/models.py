
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Workshop(models.Model):
    name = models.CharField(
        max_length=150,
        verbose_name=_("Workshop name")
    )

    slug = models.SlugField(
        max_length=160,
        unique=True
    )

    country = models.CharField(
        max_length=2,
        default="US"
    )

    default_language = models.CharField(
        max_length=10,
        choices=[
            ("en-us", "English"),
            ("it", _("Italian")),
        ],
        default="en-us"
    )

    timezone = models.CharField(
        max_length=50,
        default="America/Chicago"
    )

    currency = models.CharField(
        max_length=3,
        default="USD"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Workshop")
        verbose_name_plural = _("Workshops")

    def __str__(self):
        return self.name


class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("User"),
    )

    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("Workshop"),
    )

    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["workshop", "user"]
        verbose_name = _("Workshop membership")
        verbose_name_plural = _("Workshop memberships")

        constraints = [
            models.UniqueConstraint(
                fields=["user", "workshop"],
                name="unique_user_per_workshop",
                violation_error_message=(
                    "This user already has a membership for this workshop. "
                    "Edit the existing membership instead."
                ),
            )
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.workshop.name}"
