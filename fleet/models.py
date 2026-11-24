
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def camper_document_path(instance, filename):
    import os
    from django.utils.text import slugify
    camper = instance.camper
    key = slugify(camper.plate or camper.internal_number) or f"camper-{camper.pk}"
    return f"campers/{key}/{instance.category.code}/{os.path.basename(filename)}"


def attachment_upload_path(instance, filename):
    import os
    if instance.work_order_id:
        key = instance.work_order.ro_number
        if instance.job_id:
            key = f"{key}/jobs/{instance.job.job_number}"
        folder = f"work-orders/{key}"
    elif instance.job_id:
        folder = f"jobs/{instance.job_id}"
    else:
        folder = "uncategorized"
    return f"{folder}/{instance.category.code}/{os.path.basename(filename)}"



class Camper(models.Model):
    """Anagrafica e caratteristiche tecniche del camper."""

    FUEL_CHOICES = [
        ("DIESEL", "Diesel"),
        ("PETROL", "Benzina"),
        ("HYBRID", "Ibrido"),
        ("ELECTRIC", "Elettrico"),
        ("OTHER", "Altro"),
    ]

    TRANSMISSION_CHOICES = [
        ("MANUAL", "Manuale"),
        ("AUTOMATIC", "Automatico"),
        ("OTHER", "Altro"),
    ]

    workshop = models.ForeignKey(
        "workshops.Workshop",
        on_delete=models.CASCADE,
        related_name="campers"
    )

    owner = models.ForeignKey(
        "clientandsuppliers.CamperOwner",
        on_delete=models.PROTECT,
        related_name="campers",
        null=True,
        blank=True,
        verbose_name="Proprietario"
    )

    # Identificazione

    internal_number = models.CharField(
        max_length=30,
        verbose_name="Numero interno"
    )

    plate = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Targa"
    )

    vin = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Numero telaio (VIN)"
    )

    brand = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Marca"
    )

    model = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Modello"
    )

    registration_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Prima immatricolazione"
    )

    # Motorizzazione

    engine_brand = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Marca motore"
    )

    engine_model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Modello motore"
    )

    engine_displacement = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Cilindrata (cc)"
    )

    engine_power = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Potenza (kW)"
    )

    fuel_type = models.CharField(
        max_length=10,
        choices=FUEL_CHOICES,
        blank=True,
        verbose_name="Alimentazione"
    )

    transmission = models.CharField(
        max_length=10,
        choices=TRANSMISSION_CHOICES,
        blank=True,
        verbose_name="Cambio"
    )

    # Allestimento e capacità

    body_brand = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Marca allestimento"
    )

    body_model = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Modello allestimento"
    )

    seats = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Posti omologati"
    )

    sleeping_places = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Posti letto"
    )

    # Dimensioni e masse

    length_mm = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Lunghezza (mm)"
    )

    width_mm = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Larghezza (mm)"
    )

    height_mm = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Altezza (mm)"
    )

    tare_weight = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Massa a vuoto (kg)"
    )

    max_weight = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Massa complessiva (kg)"
    )

    # Utilizzo e manutenzione

    mileage = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Chilometraggio"
    )

    mileage_updated_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data aggiornamento chilometraggio"
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Note generali"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Attivo"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["internal_number"]
        verbose_name = "Camper"
        verbose_name_plural = "Parco mezzi"

        constraints = [
            models.UniqueConstraint(
                fields=["workshop", "internal_number"],
                name="unique_camper_number_per_workshop"
            ),
            models.UniqueConstraint(
                fields=["workshop", "plate"],
                condition=~Q(plate=""),
                name="unique_camper_plate_per_workshop"
            ),
            models.UniqueConstraint(
                fields=["workshop", "vin"],
                condition=~Q(vin=""),
                name="unique_camper_vin_per_workshop"
            ),
        ]

    def clean(self):
        super().clean()

        if self.owner_id and self.workshop_id:
            if self.owner.workshop_id != self.workshop_id:
                raise ValidationError({
                    "owner": "Il proprietario deve appartenere alla stessa officina."
                })
            if not self.owner.is_customer:
                raise ValidationError({"owner": "Il proprietario del veicolo deve essere registrato come cliente."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.internal_number} - {self.plate or self.model}"


class CamperPhoto(models.Model):
    """Fotografie associate a un camper."""

    camper = models.ForeignKey(
        Camper,
        on_delete=models.CASCADE,
        related_name="photos"
    )

    image = models.ImageField(
        upload_to=camper_document_path,
        verbose_name="Fotografia"
    )
    category = models.ForeignKey("orders.DocumentCategory", on_delete=models.PROTECT, related_name="camper_photos")

    caption = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Descrizione"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Fotografia"
        verbose_name_plural = "Fotografie"

    def __str__(self):
        return f"{self.camper.internal_number} - {self.caption}"


_LEGACY_MODEL_ALIASES = {
    "DocumentCategory": "orders",
    "WarrantyClaim": "orders",
    "WarrantyReturn": "orders",
    "JobNote": "orders",
    "Attachment": "orders",
    "Notification": "orders",
    "TimeEvent": "orders",
    "JobAssignment": "orders",
    "AuditLog": "orders",
    "JobParticipation": "orders",
    "PartsRequest": "parts",
    "JobPartUsage": "parts",
    "WarehouseNote": "parts",
    "WarehouseNoteRead": "parts",
}


def __getattr__(name):
    app_label = _LEGACY_MODEL_ALIASES.get(name)
    if app_label is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from django.apps import apps

    return apps.get_model(app_label, name)
