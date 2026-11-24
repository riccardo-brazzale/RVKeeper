
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Gestione degli utenti tramite nome utente e indirizzo email."""

    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("Username is required.")
        username = username.strip()
        if not username:
            raise ValueError("Username is required.")
        if not email:
            raise ValueError("Email address is required.")

        email = self.normalize_email(email).lower()

        user = self.model(
            username=username,
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("profile", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """Primary RVKeeper user account."""

    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name=_("Username"),
    )

    LANGUAGE_CHOICES = [
        ("", _("Use browser language")),
        ("en-us", _("English")),
        ("it", _("Italian")),
        ("es", _("Spanish")),
    ]
    PROFILE_CHOICES = [
        ("admin", _("Administrator")),
        ("warehouse", _("Warehouse operator")),
        ("mechanic", _("Mechanic")),
    ]

    email = models.EmailField(
        verbose_name=_("Email address")
    )

    preferred_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default="",
        verbose_name=_("Preferred language"),
    )

    profile = models.CharField(max_length=20, choices=PROFILE_CHOICES, default="mechanic", verbose_name=_("Profile"))

    @property
    def is_mechanic(self):
        return self.profile == "mechanic"

    @property
    def is_warehouse(self):
        return self.profile == "warehouse"

    @property
    def is_administrator(self):
        return self.profile == "admin" or self.is_superuser

    def has_perm(self, perm, obj=None):
        return self.is_administrator or super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        return self.is_administrator or super().has_module_perms(app_label)

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class AuthenticationSettings(models.Model):
    """Global authentication security settings managed from Django admin."""

    idle_timeout_minutes = models.PositiveIntegerField(
        default=15,
        verbose_name=_("Inattivita consentita (minuti)"),
    )
    session_duration_hours = models.PositiveIntegerField(
        default=10,
        verbose_name=_("Durata massima sessione (ore)"),
    )

    class Meta:
        verbose_name = _("Impostazioni di autenticazione")
        verbose_name_plural = _("Impostazioni di autenticazione")

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        settings_object, _ = cls.objects.get_or_create(pk=1)
        return settings_object
