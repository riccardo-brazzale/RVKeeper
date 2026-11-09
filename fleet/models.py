
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


class WorkOrder(models.Model):
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in (
        "open", "in_progress", "ready_inspection", "ready_pickup",
        "additional_work", "completed", "cancelled",
    )]
    CLASS_CHOICES = [("customer_pay", "A pagamento"), ("stock", "Stock")]
    WARRANTY_CHOICES = [(v, v.replace("_", " ").title()) for v in (
        "not_applicable", "pending", "approved", "partially_approved", "declined",
    )]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="work_orders")
    vehicle = models.ForeignKey(Camper, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders")
    ro_number = models.CharField(max_length=40)
    year = models.CharField(max_length=100, blank=True, help_text="Anno o nota relativa al veicolo")
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=150, blank=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_email = models.EmailField(blank=True)
    odometer = models.PositiveIntegerField(null=True, blank=True)
    work_classification = models.CharField(max_length=20, choices=CLASS_CHOICES, default="customer_pay")
    warranty_status = models.CharField(max_length=30, choices=WARRANTY_CHOICES, default="not_applicable")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="open")
    reception_notes = models.TextField(blank=True)
    checklist = models.JSONField(default=list, blank=True)
    damages = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_work_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("workshop", "ro_number"), name="unique_ro_per_workshop")]

    def __str__(self):
        return f"RO {self.ro_number} · {self.customer_name}"


class Job(models.Model):
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in (
        "not_started", "in_progress", "paused", "waiting_parts", "waiting_warranty", "completed", "cancelled",
    )]
    CATEGORY_CHOICES = [(v, v.replace("_", " ").title()) for v in ("customer_pay", "warranty", "stock")]
    DEPARTMENT_CHOICES = [(v, v.title()) for v in ("technician", "details")]
    SPECIALTY_CHOICES = [(v, v.title()) for v in ("interior", "engine", "body", "general", "detailing")]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="jobs")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="jobs")
    job_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="customer_pay")
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, default="technician")
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES, default="general")
    assigned_to = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_jobs")
    active_technician = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="active_jobs")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="not_started")
    reception_notes = models.TextField(blank=True)
    standard_minutes = models.PositiveIntegerField(default=0)
    net_minutes = models.PositiveIntegerField(default=0)
    waiting_minutes = models.PositiveIntegerField(default=0)
    active_since = models.DateTimeField(null=True, blank=True)
    waiting_started_at = models.DateTimeField(null=True, blank=True)
    block_reason = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    transfer_note = models.TextField(blank=True)
    warranty_decision = models.CharField(max_length=30, blank=True)
    warranty_hours = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    warranty_reason = models.TextField(blank=True)
    parts_ready = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("work_order", "job_number")

    def __str__(self):
        return f"RO {self.work_order.ro_number} · {self.title}"


class Part(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="parts")
    part_number = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    location = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("workshop", "part_number"), name="unique_part_number_per_workshop")]

    def __str__(self):
        return f"{self.part_number} · {self.name}"


class PartsRequest(models.Model):
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in ("new", "pending", "preparing", "ready_for_pickup", "delivered", "cancelled")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="parts_requests")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="parts_requests")
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests")
    part = models.ForeignKey(Part, on_delete=models.SET_NULL, null=True, blank=True, related_name="requests")
    custom_item = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=30, default="each")
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_delivered = models.CharField(max_length=30, blank=True)
    quantity_delivered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conversion_factor = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    repair_minutes = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    supplier = models.CharField(max_length=200, blank=True)
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
