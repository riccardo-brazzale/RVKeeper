
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.conf import settings


class CamperOwner(models.Model):
    """Anagrafica dei proprietari dei camper."""

    workshop = models.ForeignKey(
        "workshops.Workshop",
        on_delete=models.CASCADE,
        related_name="camper_owners"
    )

    is_company = models.BooleanField(
        default=False,
        verbose_name="Azienda"
    )

    first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nome"
    )

    last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Cognome"
    )

    company_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Ragione sociale"
    )

    tax_code = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Codice fiscale"
    )

    vat_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Partita IVA"
    )

    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Telefono"
    )

    email = models.EmailField(
        blank=True,
        verbose_name="Email"
    )

    address = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Indirizzo"
    )

    postal_code = models.CharField(
        max_length=15,
        blank=True,
        verbose_name="CAP"
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Città"
    )

    country = models.CharField(
        max_length=2,
        default="IT",
        verbose_name="Paese"
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Note"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["last_name", "first_name", "company_name"]
        verbose_name = "Proprietario"
        verbose_name_plural = "Proprietari"

    def __str__(self):
        if self.is_company:
            return self.company_name

        return f"{self.first_name} {self.last_name}".strip()


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
        CamperOwner,
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
        upload_to="fleet/campers/%Y/%m/",
        verbose_name="Fotografia"
    )

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
