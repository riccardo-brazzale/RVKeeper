
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from clientandsuppliers.models import CamperOwner
from parts.models import Part, PartDocument, PartMovement, PartSupplierOffer
from orders.models import Job, WorkOrder
from quotes.models import Quote, QuoteLine


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


class PartsRequest(models.Model):
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in ("new", "pending", "preparing", "ready_for_pickup", "delivered", "cancelled")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="parts_requests")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="parts_requests")
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests")
    part = models.ForeignKey(Part, on_delete=models.SET_NULL, null=True, blank=True, related_name="requests")
    supplier_offer = models.ForeignKey("PartSupplierOffer", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests", verbose_name="Offerta fornitore")
    custom_item = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=30, default="each")
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_delivered = models.CharField(max_length=30, blank=True)
    quantity_delivered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conversion_factor = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    repair_minutes = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Prezzo d'acquisto concordato")
    order_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="new")
    warranty_claim = models.ForeignKey("WarrantyClaim", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests")
    authorization = models.TextField(blank=True)
    documents = models.JSONField(default=list, blank=True)
    defect_photos = models.JSONField(default=list, blank=True)
    defect_description = models.TextField(blank=True)
    requested_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests_created")
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivered_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests_delivered")
    inventory_applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"RO {self.work_order.ro_number} · {self.part or self.custom_item}"

    def clean(self):
        super().clean()
        if self.supplier_offer_id:
            offer = self.supplier_offer
            if offer.part_id != self.part_id or (self.workshop_id and offer.part.workshop_id != self.workshop_id):
                raise ValidationError({"supplier_offer": "Scegli un’offerta associata a questo ricambio e alla stessa officina."})


class WarrantyClaim(models.Model):
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in ("submitted", "in_review", "approved", "partially_approved", "declined")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="warranty_claims")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="warranty_claims")
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_claims")
    component = models.CharField(max_length=200, blank=True)
    problem_description = models.TextField()
    work_needed = models.TextField(blank=True)
    requested_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    approved_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="submitted")
    decision_notes = models.TextField(blank=True)
    photos = models.JSONField(default=list, blank=True)
    requested_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_claims_created")
    decided_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_claims_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Garanzia RO {self.work_order.ro_number} · {self.component}"


class WarrantyReturn(models.Model):
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in ("submitted", "in_review", "return_approved", "replacement_approved", "credit_approved", "declined")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="warranty_returns")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="warranty_returns")
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_returns")
    parts_request = models.ForeignKey(PartsRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_returns")
    part_name = models.CharField(max_length=200)
    part_number = models.CharField(max_length=80, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    received_date = models.DateField(null=True, blank=True)
    defect_description = models.TextField(blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    photos = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="submitted")
    decision_notes = models.TextField(blank=True)
    decided_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_returns_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_returns_created")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reso RO {self.work_order.ro_number} · {self.part_name}"


class JobNote(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="job_notes")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="job_notes")
    department = models.CharField(max_length=30, blank=True)
    text = models.TextField()
    language = models.CharField(max_length=5, default="it")
    translations = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nota · {self.job}"


class Attachment(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="attachments")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments")
    file = models.FileField(upload_to="fleet/attachments/%Y/%m/")
    file_name = models.CharField(max_length=255)
    caption = models.CharField(max_length=250, blank=True)
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments")
    department = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name


class Notification(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="notifications")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


class TimeEvent(models.Model):
    EVENT_CHOICES = [(v, v.title()) for v in ("start", "pause", "finish", "waiting")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="time_events")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="time_events")
    mechanic = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="time_events")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    event_at = models.DateTimeField()
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-event_at",)


class JobAssignment(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="job_assignments")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="assignments")
    from_technician = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assignments_from")
    to_technician = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assignments_to")
    reason = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="audit_logs")
    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=30)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
