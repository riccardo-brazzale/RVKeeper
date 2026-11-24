from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from fleet.models import attachment_upload_path


def next_ro_number(workshop):
    """Return the next workshop-scoped repair order number.

    Callers creating an order should lock the Workshop row in a transaction so
    concurrent order creation is serialized.
    """
    year = timezone.localdate().year
    sequence = WorkOrder.objects.filter(workshop=workshop).count() + 1
    number = f"RO-{year}-{sequence:04d}"
    while WorkOrder.objects.filter(workshop=workshop, ro_number=number).exists():
        sequence += 1
        number = f"RO-{year}-{sequence:04d}"
    return number


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
        ("ready_inspection", "In attesa di controllo per fatturazione"), ("ready_pickup", "Pronto alla consegna"),
        ("additional_work", "Lavori aggiuntivi"), ("completed", "Chiuso"), ("cancelled", "Annullato"),
    ]
    CLASS_CHOICES = [("customer_pay", "A pagamento"), ("stock", "Stock")]
    WARRANTY_CHOICES = [(v, v.replace("_", " ").title()) for v in (
        "not_applicable", "pending", "approved", "partially_approved", "declined",
    )]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="work_orders")
    bom_template = models.ForeignKey(
        "BillOfMaterials",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_orders",
        verbose_name="Distinta base",
    )
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


class BillOfMaterials(models.Model):
    workshop = models.ForeignKey(
        "workshops.Workshop",
        on_delete=models.CASCADE,
        related_name="bill_of_materials",
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("workshop", "code"),
                name="unique_bom_code_per_workshop",
            ),
        ]
        verbose_name = "Distinta base"
        verbose_name_plural = "Distinte base"

    def __str__(self):
        return f"{self.code} · {self.name}"


class BillOfMaterialsLine(models.Model):
    bom = models.ForeignKey(
        BillOfMaterials,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    department = models.CharField(max_length=20, choices=[("technician", "Technician"), ("details", "Details")], default="technician")
    specialty = models.CharField(max_length=20, default="general")
    labor_article = models.ForeignKey(
        "LaborArticle",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    standard_minutes = models.PositiveIntegerField(default=0)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("sequence", "pk")
        verbose_name = "Attività distinta base"
        verbose_name_plural = "Attività distinte base"

    def __str__(self):
        return f"{self.sequence}. {self.title}"


class Job(models.Model):
    STATUS_CHOICES = [
        ("not_started", "Da iniziare"),
        ("in_progress", "In corso"),
        ("paused", "In pausa"),
        ("waiting_parts", "In attesa dei ricambi"),
        ("waiting_warranty", "In attesa della garanzia"),
        ("completed", "Chiusa"),
        ("cancelled", "Annullata"),
    ]
    CATEGORY_CHOICES = [(v, v.replace("_", " ").title()) for v in ("customer_pay", "warranty", "stock")]
    DEPARTMENT_CHOICES = [(v, v.title()) for v in ("technician", "details")]
    SPECIALTY_CHOICES = [(v, v.title()) for v in ("interior", "engine", "body", "general", "detailing")]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="jobs")
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.CASCADE, related_name="jobs")
    job_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    labor_article = models.ForeignKey("LaborArticle", on_delete=models.PROTECT, null=True, blank=True, related_name="jobs", verbose_name="Articolo manodopera")
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="customer_pay")
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, default="technician")
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES, default="general")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="not_started")
    invoice_hourly_rate_override = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Tariffa oraria fatturata",
    )
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

    def clean(self):
        super().clean()
        if self.invoice_hourly_rate_override is not None and self.invoice_hourly_rate_override < 0:
            raise ValidationError({"invoice_hourly_rate_override": _("Prices cannot be negative.")})

    def __str__(self):
        return f"RO {self.work_order.ro_number} · {self.title}"


class LaborArticle(models.Model):
    """Singola tariffa oraria del catalogo manodopera."""
    TARIFF_CHOICES = [(v, label) for v, label in (
        ("standard", "Standard"), ("holiday", "Festiva"), ("discounted", "Scontata"),
    )]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="labor_articles")
    code = models.CharField(max_length=40)
    description = models.CharField(max_length=200)
    tariff_type = models.CharField(max_length=20, choices=TARIFF_CHOICES, default="standard", verbose_name="Tipologia tariffa")
    is_active = models.BooleanField(default=True, verbose_name="Attivo")

    class Meta:
        ordering = ("code",)
        constraints = [models.UniqueConstraint(fields=("workshop", "code"), name="unique_labor_article_per_workshop")]
        verbose_name = "Articolo manodopera"
        verbose_name_plural = "Articoli manodopera"

    def __str__(self):
        return f"{self.code} · {self.description} ({self.get_tariff_type_display()})"


class PriceList(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="price_lists")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    current_valid_from = models.DateField(
        default=timezone.localdate,
        verbose_name="Data validità attuale",
    )
    future_valid_from = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data validità futura",
    )
    customer = models.ForeignKey(
        "clientandsuppliers.CamperOwner", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="associated_price_lists", verbose_name="Codice cliente associato",
    )
    is_default = models.BooleanField(default=False, verbose_name="Listino generico")
    is_workshop = models.BooleanField(default=False, verbose_name="Listino officina")
    is_active = models.BooleanField(default=True, verbose_name="Attivo")

    class Meta:
        ordering = ("name", "code")
        constraints = [
            models.UniqueConstraint(fields=("workshop", "code"), name="unique_price_list_code_per_workshop"),
            models.UniqueConstraint(fields=("workshop",), condition=models.Q(is_default=True), name="one_default_price_list_per_workshop"),
            models.UniqueConstraint(fields=("workshop",), condition=models.Q(is_workshop=True), name="one_workshop_price_list_per_workshop"),
        ]

    def clean(self):
        super().clean()
        if self.customer_id and self.customer.workshop_id != self.workshop_id:
            raise ValidationError({"customer": _("The customer must belong to the same workshop as the price list.")})
        if self.customer_id and (self.is_default or self.is_workshop):
            raise ValidationError({"customer": _("CLIENTE and OFFICINE price lists cannot be assigned to a single customer.")})
        if self.customer_id and self.code != self.customer.customer_code:
            raise ValidationError({"code": _("A customer price list must use the customer's code.")})
        if self.is_default and self.is_workshop:
            raise ValidationError({"is_workshop": _("A price list cannot be both CLIENTE and OFFICINE.")})
        if self.is_default and not self.is_active:
            raise ValidationError({"is_active": _("The CLIENTE price list must stay active.")})

    def __str__(self):
        return f"{self.code} · {self.name}"


class PriceListItem(models.Model):
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="items")
    part = models.ForeignKey("parts.Part", on_delete=models.CASCADE, null=True, blank=True, related_name="price_list_items")
    labor_article = models.ForeignKey(LaborArticle, on_delete=models.CASCADE, null=True, blank=True, related_name="price_list_items")
    article_class = models.ForeignKey("parts.ArticleClass", on_delete=models.CASCADE, null=True, blank=True, related_name="price_list_items")
    article_group = models.ForeignKey("parts.ArticleGroup", on_delete=models.CASCADE, null=True, blank=True, related_name="price_list_items")
    previous_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Prezzo precedente",
    )
    previous_valid_from = models.DateField(null=True, blank=True, verbose_name="Precedente valido dal")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prezzo corrente")
    valid_from = models.DateField(default=timezone.localdate, verbose_name="Corrente valido dal")
    future_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Prezzo futuro",
    )
    future_valid_from = models.DateField(null=True, blank=True, verbose_name="Futuro valido dal")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(part__isnull=False, labor_article__isnull=True, article_class__isnull=True, article_group__isnull=True)
                    | models.Q(part__isnull=True, labor_article__isnull=False, article_class__isnull=True, article_group__isnull=True)
                    | models.Q(part__isnull=True, labor_article__isnull=True, article_class__isnull=False, article_group__isnull=True)
                    | models.Q(part__isnull=True, labor_article__isnull=True, article_class__isnull=True, article_group__isnull=False)
                ),
                name="price_list_item_has_one_catalog_target",
            ),
            models.UniqueConstraint(fields=("price_list", "part"), condition=models.Q(part__isnull=False), name="unique_part_per_price_list"),
            models.UniqueConstraint(fields=("price_list", "labor_article"), condition=models.Q(labor_article__isnull=False), name="unique_labor_per_price_list"),
            models.UniqueConstraint(fields=("price_list", "article_class"), condition=models.Q(article_class__isnull=False), name="unique_article_class_per_price_list"),
            models.UniqueConstraint(fields=("price_list", "article_group"), condition=models.Q(article_group__isnull=False), name="unique_article_group_per_price_list"),
            models.CheckConstraint(
                condition=(
                    models.Q(previous_price__isnull=True, previous_valid_from__isnull=True)
                    | models.Q(previous_price__isnull=False, previous_valid_from__isnull=False)
                ),
                name="previous_price_has_matching_date",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(previous_valid_from__isnull=True)
                    | models.Q(previous_valid_from__lt=models.F("valid_from"))
                ),
                name="previous_price_date_before_current",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(future_valid_from__isnull=True)
                    | models.Q(future_valid_from__gt=models.F("valid_from"))
                ),
                name="future_price_date_after_current",
            ),
        ]

    def clean(self):
        super().clean()
        if self.previous_price is not None and self.previous_price < 0:
            raise ValidationError({"previous_price": _("Prices cannot be negative.")})
        if self.unit_price < 0:
            raise ValidationError({"unit_price": _("Prices cannot be negative.")})
        if self.future_price is not None and self.future_price < 0:
            raise ValidationError({"future_price": _("Prices cannot be negative.")})
        if (self.previous_price is None) != (self.previous_valid_from is None):
            raise ValidationError(_("The previous price and its start date must be set together."))
        if self.previous_valid_from and self.previous_valid_from >= self.valid_from:
            raise ValidationError({"previous_valid_from": _("The previous price must start before the current price.")})
        if self.future_valid_from and self.future_valid_from <= self.valid_from:
            raise ValidationError({"future_valid_from": _("The future price must start after the current price.")})
        targets = [self.part_id, self.labor_article_id, self.article_class_id, self.article_group_id]
        if sum(1 for t in targets if t) != 1:
            raise ValidationError(_("Select exactly one part, labor article, article class or article group."))
        if self.price_list_id:
            if self.part_id and self.part.workshop_id != self.price_list.workshop_id:
                raise ValidationError({"part": _("The part must belong to the price list workshop.")})
            if self.labor_article_id and self.labor_article.workshop_id != self.price_list.workshop_id:
                raise ValidationError({"labor_article": _("The labor article must belong to the price list workshop.")})
            if self.article_class_id and self.article_class.workshop_id != self.price_list.workshop_id:
                raise ValidationError({"article_class": _("The article class must belong to the price list workshop.")})
            if self.article_group_id and self.article_group.workshop_id != self.price_list.workshop_id:
                raise ValidationError({"article_group": _("The article group must belong to the price list workshop.")})

    def price_for_date(self, effective_date):
        versions = (
            (self.previous_valid_from, self.previous_price),
            (self.valid_from, self.unit_price),
            (self.future_valid_from, self.future_price),
        )
        applicable = [
            (valid_from, price)
            for valid_from, price in versions
            if valid_from is not None and price is not None and valid_from <= effective_date
        ]
        return max(applicable, key=lambda version: version[0])[1] if applicable else None


class CustomerItemDiscount(models.Model):
    customer = models.ForeignKey("clientandsuppliers.CamperOwner", on_delete=models.CASCADE, related_name="item_discounts")
    part = models.ForeignKey("parts.Part", on_delete=models.CASCADE, null=True, blank=True, related_name="customer_discounts")
    labor_article = models.ForeignKey(LaborArticle, on_delete=models.CASCADE, null=True, blank=True, related_name="customer_discounts")
    article_class = models.ForeignKey("parts.ArticleClass", on_delete=models.CASCADE, null=True, blank=True, related_name="customer_discounts")
    article_group = models.ForeignKey("parts.ArticleGroup", on_delete=models.CASCADE, null=True, blank=True, related_name="customer_discounts")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Sconto cliente (%)")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(part__isnull=False, labor_article__isnull=True, article_class__isnull=True, article_group__isnull=True)
                    | models.Q(part__isnull=True, labor_article__isnull=False, article_class__isnull=True, article_group__isnull=True)
                    | models.Q(part__isnull=True, labor_article__isnull=True, article_class__isnull=False, article_group__isnull=True)
                    | models.Q(part__isnull=True, labor_article__isnull=True, article_class__isnull=True, article_group__isnull=False)
                ),
                name="customer_discount_has_one_catalog_target",
            ),
            models.UniqueConstraint(fields=("customer", "part"), condition=models.Q(part__isnull=False), name="unique_customer_part_discount"),
            models.UniqueConstraint(fields=("customer", "labor_article"), condition=models.Q(labor_article__isnull=False), name="unique_customer_labor_discount"),
            models.UniqueConstraint(fields=("customer", "article_class"), condition=models.Q(article_class__isnull=False), name="unique_customer_article_class_discount"),
            models.UniqueConstraint(fields=("customer", "article_group"), condition=models.Q(article_group__isnull=False), name="unique_customer_article_group_discount"),
        ]

    def clean(self):
        super().clean()
        if self.discount_percent is not None and not 0 <= self.discount_percent <= 100:
            raise ValidationError({"discount_percent": _("The discount must be between 0 and 100%.")})
        if self.customer_id and not self.customer.is_customer:
            raise ValidationError({"customer": _("Select a customer.")})
        targets = [self.part_id, self.labor_article_id, self.article_class_id, self.article_group_id]
        if sum(1 for t in targets if t) != 1:
            raise ValidationError(_("Select exactly one part, labor article, article class or article group."))
        if self.customer_id:
            if self.part_id and self.part.workshop_id != self.customer.workshop_id:
                raise ValidationError({"part": _("The part must belong to the customer's workshop.")})
            if self.labor_article_id and self.labor_article.workshop_id != self.customer.workshop_id:
                raise ValidationError({"labor_article": _("The labor article must belong to the customer's workshop.")})
            if self.article_class_id and self.article_class.workshop_id != self.customer.workshop_id:
                raise ValidationError({"article_class": _("The article class must belong to the customer's workshop.")})
            if self.article_group_id and self.article_group.workshop_id != self.customer.workshop_id:
                raise ValidationError({"article_group": _("The article group must belong to the customer's workshop.")})


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
class DocumentCategory(models.Model):
    """Categorie di documenti gestite dall'amministrazione."""
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=250, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name = "Categoria documento"
        verbose_name_plural = "Categorie documenti"

    def __str__(self):
        return self.name


class WarrantyClaim(models.Model):
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in ("submitted", "in_review", "approved", "partially_approved", "declined")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="warranty_claims")
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.CASCADE, related_name="warranty_claims")
    job = models.ForeignKey("orders.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_claims")
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
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.CASCADE, related_name="warranty_returns")
    job = models.ForeignKey("orders.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_returns")
    parts_request = models.ForeignKey("parts.PartsRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="warranty_returns")
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
    job = models.ForeignKey("orders.Job", on_delete=models.CASCADE, related_name="notes")
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
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.CASCADE, null=True, blank=True, related_name="attachments")
    job = models.ForeignKey("orders.Job", on_delete=models.CASCADE, null=True, blank=True, related_name="attachments")
    category = models.ForeignKey(DocumentCategory, on_delete=models.PROTECT, related_name="work_attachments")
    file = models.FileField(upload_to=attachment_upload_path)
    file_name = models.CharField(max_length=255)
    caption = models.CharField(max_length=250, blank=True)
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments")
    department = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if not self.work_order_id and not self.job_id:
            raise ValidationError("Collega l'allegato a un ordine di lavoro o a una lavorazione.")
        if self.work_order_id and self.job_id and self.job.work_order_id != self.work_order_id:
            raise ValidationError("La lavorazione selezionata non appartiene all'ordine scelto.")
        if self.work_order_id and self.job_id and self.job.work_order_id != self.work_order_id:
            raise ValidationError("La lavorazione selezionata non appartiene all'ordine scelto.")
        if self.work_order_id and self.job_id and self.job.work_order_id != self.work_order_id:
            raise ValidationError("La lavorazione selezionata non appartiene all'ordine scelto.")

    def __str__(self):
        return self.file_name


class Notification(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="notifications")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


class TimeEvent(models.Model):
    EVENT_CHOICES = [(v, v.title()) for v in ("start", "pause", "resume", "finish", "waiting", "reopen")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="time_events")
    job = models.ForeignKey("orders.Job", on_delete=models.CASCADE, related_name="time_events")
    mechanic = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="time_events")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    pause_reason = models.ForeignKey("orders.PauseReason", on_delete=models.PROTECT, null=True, blank=True, related_name="time_events")
    event_at = models.DateTimeField()
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-event_at",)


class JobAssignment(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="job_assignments")
    job = models.ForeignKey("orders.Job", on_delete=models.CASCADE, related_name="assignments")
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
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class JobParticipation(models.Model):
    """Partecipazione individuale: più tecnici possono lavorare sullo stesso Job."""
    SOURCE_CHOICES = [("assigned", "Chiamata/assegnazione"), ("self", "Iniziativa propria")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="job_participations")
    job = models.ForeignKey("orders.Job", on_delete=models.CASCADE, related_name="participations")
    mechanic = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="job_participations")
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="assigned")
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("job", "mechanic"), condition=models.Q(is_active=True), name="unique_active_job_mechanic")]
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.mechanic} · {self.job}"
