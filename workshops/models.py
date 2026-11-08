
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Workshop(models.Model):
    name = models.CharField(
        max_length=150,
        verbose_name="Nome officina"
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
            ("it", "Italiano"),
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
        verbose_name = "Officina"
        verbose_name_plural = "Officine"

    def __str__(self):
        return self.name


class Role(models.Model):
    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name="roles"
    )

    name = models.CharField(max_length=100)

    code = models.SlugField(max_length=50)

    description = models.TextField(blank=True)

    permissions = models.ManyToManyField(
        "auth.Permission",
        blank=True,
        related_name="rvkeeper_roles"
    )

    is_system = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Ruolo"
        verbose_name_plural = "Ruoli"

        constraints = [
            models.UniqueConstraint(
                fields=["workshop", "code"],
                name="unique_role_code_per_workshop"
            )
        ]

    def __str__(self):
        return f"{self.workshop.name} - {self.name}"


class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="memberships"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["workshop", "user"]
        verbose_name = "Appartenenza"
        verbose_name_plural = "Appartenenze"

        constraints = [
            models.UniqueConstraint(
                fields=["user", "workshop"],
                name="unique_user_per_workshop"
            )
        ]

    def clean(self):
        super().clean()

        if (
            self.role_id
            and self.workshop_id
            and self.role.workshop_id != self.workshop_id
        ):
            raise ValidationError({
                "role": "Il ruolo deve appartenere alla stessa officina."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.workshop.name}"
