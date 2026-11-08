
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    """Gestione degli utenti tramite indirizzo email."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'indirizzo email è obbligatorio")

        email = self.normalize_email(email).lower()

        user = self.model(
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Il superuser deve avere is_staff=True")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Il superuser deve avere is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Utente principale di RVKeeper."""

    username = None

    LANGUAGE_CHOICES = [
        ("en-us", "English"),
        ("it", "Italiano"),
    ]

    email = models.EmailField(
        unique=True,
        verbose_name="Email"
    )

    preferred_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default="en-us",
        verbose_name="Lingua preferita"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
