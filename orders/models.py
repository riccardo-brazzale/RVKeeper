from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class PauseReason(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "label")
        verbose_name = "Causale pausa"
        verbose_name_plural = "Causali pausa"

    def __str__(self):
        return self.label


class WorkOrder(models.Model):
    STATUS_CHOICES = [
        ("open", "Aperto"), ("in_progress", "In lavorazione"),
        ("ready_inspection", "In attesa di collaudo"), ("ready_pickup", "Pronto alla consegna"),
        ("additional_work", "Lavori aggiuntivi"), ("completed", "Chiuso"), ("cancelled", "Annullato"),
    ]
    CLASS_CHOICES = [("customer_pay", "A pagamento"), ("stock", "Stock")]
    WARRANTY_CHOICES = [(v, v.replace("_", " ").title()) for v in (
        "not_applicable", "pending", "approved", "partially_approved", "declined",
    )]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="work_orders")
    customer = models.ForeignKey("clientandsuppliers.CamperOwner", on_delete=models.PROTECT, null=True, blank=True, related_name="work_orders", verbose_name="Cliente")
    vehicle = models.ForeignKey("fleet.Camper", on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders")
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
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Data chiusura")
    invoiced = models.BooleanField(default=False, verbose_name="Fatturato")
    invoiced_at = models.DateTimeField(null=True, blank=True, verbose_name="Data fatturazione")
    invoiced_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders_invoiced")
    reception_notes = models.TextField(blank=True)
    checklist = models.JSONField(default=list, blank=True)
    damages = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_work_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("workshop", "ro_number"), name="unique_ro_per_workshop")]

    def clean(self):
        super().clean()
        if not self.vehicle_id:
            raise ValidationError({"vehicle": _("A work order must be opened for a camper.")})
        if self.customer_id and ((self.workshop_id and self.customer.workshop_id != self.workshop_id) or not self.customer.is_customer):
            raise ValidationError({"customer": _("Select a customer from the same workshop.")})
        if self.workshop_id and self.vehicle.workshop_id != self.workshop_id:
            raise ValidationError({"vehicle": _("Select a camper from the same workshop.")})
        if not self.vehicle.owner_id or not self.vehicle.owner.is_customer:
            raise ValidationError({"vehicle": _("A work order requires a camper assigned to a customer.")})
        if self.customer_id and self.vehicle.owner_id != self.customer_id:
            raise ValidationError({"customer": _("The customer must be the camper's owner.")})

    def __str__(self):
        return f"RO {self.ro_number} · {self.vehicle or self.customer or self.customer_name}"


class Job(models.Model):
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in (
        "not_started", "in_progress", "paused", "waiting_parts", "waiting_warranty", "completed", "cancelled",
    )]
    CATEGORY_CHOICES = [(v, v.replace("_", " ").title()) for v in ("customer_pay", "warranty", "stock")]
    DEPARTMENT_CHOICES = [(v, v.title()) for v in ("technician", "details")]
    SPECIALTY_CHOICES = [(v, v.title()) for v in ("interior", "engine", "body", "general", "detailing")]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="jobs")
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.CASCADE, related_name="jobs")
    job_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="customer_pay")
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, default="technician")
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES, default="general")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="not_started")
    reception_notes = models.TextField(blank=True)
    standard_minutes = models.PositiveIntegerField(default=0)
    block_reason = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
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


class JobCall(models.Model):
    """Chiamata personale a un tecnico per partecipare a una lavorazione."""
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="job_calls")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="calls")
    mechanic = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="job_calls")
    called_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, related_name="calls_created")
    accepted_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Chiamata {self.mechanic} · {self.job}"
