from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def part_document_path(instance, filename):
    import os
    from django.utils.text import slugify
    key = slugify(instance.part.part_number) or f"part-{instance.part_id}"
    return f"parts/{key}/{instance.category.code}/{os.path.basename(filename)}"


class ArticleClass(models.Model):
    """Classe merceologica (es. Batterie, Freni, Elettronica, Meccanica...)."""
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="article_classes")
    code = models.CharField(max_length=40, verbose_name="Codice")
    name = models.CharField(max_length=100, verbose_name="Nome")
    is_active = models.BooleanField(default=True, verbose_name="Attiva")

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("workshop", "code"), name="unique_article_class_per_workshop"),
        ]
        verbose_name = "Classe merceologica"
        verbose_name_plural = "Classi merceologiche"

    def __str__(self):
        return f"{self.code} · {self.name}"


class ArticleGroup(models.Model):
    """Gruppo articolo che appartiene a una classe merceologica (es. Batterie nichel-cadmio)."""
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="article_groups")
    article_class = models.ForeignKey(
        ArticleClass, on_delete=models.PROTECT, related_name="groups", verbose_name="Classe merceologica"
    )
    code = models.CharField(max_length=40, verbose_name="Codice")
    name = models.CharField(max_length=100, verbose_name="Nome")
    is_active = models.BooleanField(default=True, verbose_name="Attivo")

    class Meta:
        ordering = ("article_class", "name")
        constraints = [
            models.UniqueConstraint(fields=("workshop", "code"), name="unique_article_group_per_workshop"),
        ]
        verbose_name = "Gruppo articolo"
        verbose_name_plural = "Gruppi articolo"

    def __str__(self):
        return f"{self.article_class.code} > {self.code} · {self.name}"


class Part(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="parts")
    part_number = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=30, default="pz", verbose_name="Unità di misura")
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Costo unitario")
    standard_minutes = models.PositiveIntegerField(default=0, verbose_name="Tempo standard (minuti)")
    article_class = models.ForeignKey(
        ArticleClass,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="parts",
        verbose_name="Classe merceologica",
    )
    article_group = models.ForeignKey(
        ArticleGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="parts",
        verbose_name="Gruppo articolo",
    )
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

    def save(self, *args, **kwargs):
        # Assegnazione automatica classe merceologica e gruppo articolo generici
        if not self.article_class_id and self.workshop_id:
            article_class, _ = ArticleClass.objects.get_or_create(
                workshop=self.workshop,
                code="GENERIC",
                defaults={"name": "Generico", "is_active": True},
            )
            self.article_class = article_class
        if not self.article_group_id and self.workshop_id and self.article_class_id:
            article_group, _ = ArticleGroup.objects.get_or_create(
                workshop=self.workshop,
                article_class=self.article_class,
                code="VARIE",
                defaults={"name": "Varie", "is_active": True},
            )
            self.article_group = article_group
        super().save(*args, **kwargs)


class PartSupplierOffer(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name="supplier_offers")
    supplier = models.ForeignKey("clientandsuppliers.CamperOwner", on_delete=models.PROTECT, related_name="part_offers")
    supplier_code = models.CharField(
        max_length=100, blank=True, db_index=True, verbose_name="Codice fornitore",
    )
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prezzo d'acquisto")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Sconto (%)")
    minimum_order_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name="Quantità minima")
    package_multiple = models.DecimalField(
        max_digits=12, decimal_places=2, default=1, verbose_name="Multiplo confezione"
    )
    lead_time_days = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Tempi di consegna (giorni)")
    is_preferred = models.BooleanField(default=False, verbose_name="Fornitore preferito")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("purchase_price", "supplier__company_name", "supplier__last_name")
        constraints = [
            models.UniqueConstraint(fields=("part", "supplier"), name="unique_supplier_offer_per_part"),
            models.CheckConstraint(
                condition=models.Q(package_multiple__gt=0),
                name="supplier_offer_package_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.purchase_price < 0:
            raise ValidationError({"purchase_price": "Il prezzo d'acquisto non può essere negativo."})
        if self.discount_percent < 0 or self.discount_percent > 100:
            raise ValidationError({"discount_percent": "Lo sconto deve essere compreso tra 0 e 100%."})
        if self.minimum_order_quantity <= 0:
            raise ValidationError({"minimum_order_quantity": "La quantità minima deve essere maggiore di zero."})
        if self.package_multiple <= 0:
            raise ValidationError({"package_multiple": "Il multiplo confezione deve essere maggiore di zero."})
        if self.part_id and self.supplier_id:
            if self.part.workshop_id != self.supplier.workshop_id:
                raise ValidationError({"supplier": "Il fornitore deve appartenere alla stessa officina del ricambio."})
            if not self.supplier.is_supplier:
                raise ValidationError({"supplier": "Seleziona un contatto registrato come fornitore."})

    def __str__(self):
        return f"{self.part} · {self.supplier} · {self.net_purchase_price} netto"

    @property
    def net_purchase_price(self):
        return (self.purchase_price * (1 - self.discount_percent / 100)).quantize(self.purchase_price.__class__("0.01"))


class TransferSlip(models.Model):
    """Bolla aperta che registra i ricambi impegnati per un ordine di lavoro."""
    STATUS_CHOICES = [
        ("open", "Aperta"),
        ("closed", "Chiusa"),
        ("cancelled", "Annullata"),
    ]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="transfer_slips")
    work_order = models.OneToOneField(
        "orders.WorkOrder", on_delete=models.CASCADE, related_name="transfer_slip",
        verbose_name="Ordine di lavoro",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open", verbose_name="Stato")
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="transfer_slips_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Bolla di trasferimento"
        verbose_name_plural = "Bolle di trasferimento"

    def __str__(self):
        return f"Bolla {self.work_order.ro_number}"

    def clean(self):
        super().clean()
        if self.work_order_id and self.workshop_id and self.work_order.workshop_id != self.workshop_id:
            raise ValidationError({"work_order": "L'ordine deve appartenere alla stessa officina."})


class TransferSlipLine(models.Model):
    """Quantità richiesta e impegnata sulla bolla di trasferimento."""
    STATUS_CHOICES = [
        ("waiting_stock", "In attesa di disponibilità"),
        ("reserved", "Impegnata"),
        ("consumed", "Scaricata"),
        ("released", "Impegno rilasciato"),
    ]

    transfer_slip = models.ForeignKey(TransferSlip, on_delete=models.CASCADE, related_name="lines")
    job = models.ForeignKey(
        "orders.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="transfer_slip_lines",
    )
    parts_request = models.OneToOneField(
        "parts.PartsRequest", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transfer_slip_line",
    )
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="transfer_slip_lines")
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Quantità richiesta")
    quantity_reserved = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Quantità impegnata",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting_stock", verbose_name="Stato")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_requested__gt=0),
                name="transfer_line_requested_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(quantity_reserved__gte=0)
                    & models.Q(quantity_reserved__lte=models.F("quantity_requested"))
                ),
                name="transfer_line_reserved_valid",
            ),
        ]
        verbose_name = "Riga bolla di trasferimento"
        verbose_name_plural = "Righe bolla di trasferimento"

    def clean(self):
        super().clean()
        if self.transfer_slip_id and self.part_id:
            if self.transfer_slip.workshop_id != self.part.workshop_id:
                raise ValidationError({"part": "Il ricambio deve appartenere alla stessa officina."})
        if self.job_id and self.transfer_slip_id:
            if self.job.work_order_id != self.transfer_slip.work_order_id:
                raise ValidationError({"job": "L'attività deve appartenere all'ordine della bolla."})
        if self.parts_request_id and self.transfer_slip_id:
            if self.parts_request.work_order_id != self.transfer_slip.work_order_id:
                raise ValidationError({"parts_request": "La richiesta deve appartenere all'ordine della bolla."})
            if self.parts_request.part_id != self.part_id:
                raise ValidationError({"part": "Il ricambio deve corrispondere alla richiesta."})
            if self.job_id and self.parts_request.job_id != self.job_id:
                raise ValidationError({"job": "L'attività deve corrispondere alla richiesta."})


class PurchaseOrder(models.Model):
    """Ordine d'acquisto emesso a un fornitore."""
    STATUS_CHOICES = [
        ("open", "Aperto"),
        ("sent", "Inviato"),
        ("partially_received", "Ricevuto parzialmente"),
        ("closed", "Saldato"),
        ("cancelled", "Annullato"),
    ]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="purchase_orders")
    supplier = models.ForeignKey(
        "clientandsuppliers.CamperOwner", on_delete=models.PROTECT, related_name="purchase_orders",
        verbose_name="Fornitore",
    )
    order_number = models.CharField(max_length=40, verbose_name="Numero ordine")
    order_date = models.DateField(verbose_name="Data ordine")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", verbose_name="Stato")
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, verbose_name="Note")

    class Meta:
        ordering = ("-order_date", "-pk")
        permissions = [
            ("manage_supplier_purchasing", "Può gestire gli acquisti dai fornitori"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("workshop", "order_number"), name="unique_purchase_order_number_per_workshop",
            ),
        ]
        indexes = [
            models.Index(fields=("workshop", "status", "supplier"), name="purchase_open_supplier_idx"),
        ]
        verbose_name = "Ordine fornitore"
        verbose_name_plural = "Ordini fornitori"

    def clean(self):
        super().clean()
        if self.supplier_id and self.workshop_id:
            if self.supplier.workshop_id != self.workshop_id or not self.supplier.is_supplier:
                raise ValidationError({"supplier": "Seleziona un fornitore della stessa officina."})

    def __str__(self):
        return self.order_number


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="purchase_order_lines")
    supplier_offer = models.ForeignKey(
        PartSupplierOffer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="purchase_order_lines",
    )
    supplier_article_code = models.CharField(max_length=100, blank=True, verbose_name="Codice articolo fornitore")
    quantity_required = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Quantità necessaria")
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Quantità ordinata")
    quantity_received = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Quantità ricevuta",
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Prezzo unitario")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Sconto (%)")

    class Meta:
        ordering = ("part__part_number", "pk")
        constraints = [
            models.UniqueConstraint(fields=("purchase_order", "part"), name="unique_part_per_purchase_order"),
            models.CheckConstraint(
                condition=(
                    models.Q(quantity_required__gt=0)
                    & models.Q(quantity_ordered__gt=0)
                    & models.Q(quantity_received__gte=0)
                    & models.Q(quantity_received__lte=models.F("quantity_ordered"))
                ),
                name="purchase_line_quantities_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="purchase_line_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_percent__gte=0, discount_percent__lte=100),
                name="purchase_line_discount_valid",
            ),
        ]
        verbose_name = "Riga ordine fornitore"
        verbose_name_plural = "Righe ordine fornitore"

    def clean(self):
        super().clean()
        if self.purchase_order_id and self.part_id:
            if self.purchase_order.workshop_id != self.part.workshop_id:
                raise ValidationError({"part": "Il ricambio deve appartenere alla stessa officina."})
        if self.supplier_offer_id and self.part_id and self.supplier_offer.part_id != self.part_id:
            raise ValidationError({"supplier_offer": "L'offerta deve corrispondere al ricambio."})
        if self.supplier_offer_id and self.purchase_order_id:
            if self.supplier_offer.supplier_id != self.purchase_order.supplier_id:
                raise ValidationError({"supplier_offer": "L'offerta deve appartenere al fornitore dell'ordine."})


class PurchaseOrderDemand(models.Model):
    """Quota di fabbisogno di una richiesta ricambi assegnata a una riga d'acquisto."""
    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.CASCADE, related_name="demands",
    )
    parts_request = models.ForeignKey(
        "parts.PartsRequest", on_delete=models.PROTECT, related_name="purchase_order_demands",
    )
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Quantità richiesta")
    quantity_received = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Quantità ricevuta",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("purchase_order_line", "parts_request"), name="unique_request_per_purchase_line",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(quantity_requested__gt=0)
                    & models.Q(quantity_received__gte=0)
                    & models.Q(quantity_received__lte=models.F("quantity_requested"))
                ),
                name="purchase_demand_quantities_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.purchase_order_line_id and self.parts_request_id:
            order = self.purchase_order_line.purchase_order
            request = self.parts_request
            if request.work_order.workshop_id != order.workshop_id:
                raise ValidationError({"parts_request": "La richiesta deve appartenere alla stessa officina."})
            if request.part_id != self.purchase_order_line.part_id:
                raise ValidationError({"parts_request": "La richiesta deve riguardare lo stesso ricambio."})


class GoodsReceipt(models.Model):
    """Bolla di entrata merce collegata a un ordine fornitore."""
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="goods_receipts")
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="goods_receipts",
        verbose_name="Ordine fornitore",
    )
    receipt_number = models.CharField(max_length=40, verbose_name="Numero bolla")
    received_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="goods_receipts_recorded",
    )
    notes = models.TextField(blank=True, verbose_name="Note")

    class Meta:
        ordering = ("-received_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("workshop", "receipt_number"), name="unique_goods_receipt_number_per_workshop",
            ),
        ]
        verbose_name = "Bolla di entrata merce"
        verbose_name_plural = "Bolle di entrata merce"

    def clean(self):
        super().clean()
        if self.purchase_order_id and self.workshop_id:
            if self.purchase_order.workshop_id != self.workshop_id:
                raise ValidationError({"purchase_order": "L'ordine deve appartenere alla stessa officina."})

    def __str__(self):
        return self.receipt_number


class GoodsReceiptLine(models.Model):
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipt_lines",
    )
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Quantità ricevuta")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("goods_receipt", "purchase_order_line"), name="unique_order_line_per_receipt",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_received__gt=0),
                name="goods_receipt_quantity_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.goods_receipt_id and self.purchase_order_line_id:
            if self.goods_receipt.purchase_order_id != self.purchase_order_line.purchase_order_id:
                raise ValidationError({"purchase_order_line": "La riga deve appartenere all'ordine della bolla."})


class SupplierPriceList(models.Model):
    """Listino fornitore con un intervallo di validità."""
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="supplier_price_lists")
    supplier = models.ForeignKey(
        "clientandsuppliers.CamperOwner", on_delete=models.PROTECT, related_name="supplier_price_lists",
        verbose_name="Fornitore",
    )
    code = models.CharField(max_length=80, verbose_name="Codice listino")
    name = models.CharField(max_length=160, blank=True, verbose_name="Nome listino")
    valid_from = models.DateField(verbose_name="Valido dal")
    valid_to = models.DateField(null=True, blank=True, verbose_name="Valido fino al")
    is_active = models.BooleanField(default=True, verbose_name="Attivo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("supplier", "-valid_from", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("workshop", "supplier", "code"), name="unique_supplier_price_list_code",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")),
                name="supplier_price_list_dates_valid",
            ),
        ]
        indexes = [
            models.Index(fields=("workshop", "supplier", "is_active", "valid_from"), name="supplier_price_valid_idx"),
        ]
        verbose_name = "Listino fornitore"
        verbose_name_plural = "Listini fornitori"

    def clean(self):
        super().clean()
        if self.supplier_id and self.workshop_id:
            if self.supplier.workshop_id != self.workshop_id or not self.supplier.is_supplier:
                raise ValidationError({"supplier": "Seleziona un fornitore della stessa officina."})
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError({"valid_to": "La data finale deve essere uguale o successiva alla data iniziale."})

    def __str__(self):
        return f"{self.supplier} · {self.code}"


class SupplierPriceListItem(models.Model):
    price_list = models.ForeignKey(SupplierPriceList, on_delete=models.CASCADE, related_name="items")
    supplier_article_code = models.CharField(max_length=100, db_index=True, verbose_name="Codice articolo fornitore")
    internal_article_code = models.CharField(max_length=80, blank=True, verbose_name="Codice di conversione interno")
    part = models.ForeignKey(
        Part, on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_price_list_items",
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prezzo unitario")
    valid_from = models.DateField(default=timezone.localdate, verbose_name="Prezzo corrente valido dal")
    previous_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Prezzo precedente")
    previous_valid_from = models.DateField(null=True, blank=True, verbose_name="Precedente valido dal")
    future_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Prezzo futuro")
    future_valid_from = models.DateField(null=True, blank=True, verbose_name="Futuro valido dal")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Sconto (%)")

    class Meta:
        ordering = ("supplier_article_code", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("price_list", "supplier_article_code"), name="unique_supplier_code_per_price_list",
            ),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="supplier_price_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(discount_percent__gte=0, discount_percent__lte=100),
                name="supplier_discount_valid",
            ),
        ]
        indexes = [
            models.Index(fields=("internal_article_code",), name="supplier_internal_code_idx"),
        ]
        verbose_name = "Riga listino fornitore"
        verbose_name_plural = "Righe listino fornitore"

    def clean(self):
        super().clean()
        if self.part_id and self.price_list_id and self.part.workshop_id != self.price_list.workshop_id:
            raise ValidationError({"part": "Il ricambio deve appartenere alla stessa officina."})


class PartDocument(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name="documents")
    category = models.ForeignKey("orders.DocumentCategory", on_delete=models.PROTECT, related_name="part_documents")
    file = models.FileField(upload_to=part_document_path)
    caption = models.CharField(max_length=200, blank=True, verbose_name="Descrizione")
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()


class PartMovement(models.Model):
    """Movimento di magazzino immutabile, collegabile a un ordine di lavoro."""
    TYPES = [("in", "Carico"), ("out", "Scarico"), ("adjustment", "Rettifica")]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="part_movements")
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="movements")
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="part_movements")
    movement_type = models.CharField(max_length=12, choices=TYPES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.CharField(max_length=250, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_movement_type_display()} · {self.part} · {self.quantity}"
class PartsRequest(models.Model):
    STATUS_CHOICES = [
        ("new", _("New")),
        ("pending", _("Pending")),
        ("preparing", _("Preparing")),
        ("on_hold", _("On hold")),
        ("ready_for_pickup", _("Ready for pickup")),
        ("delivered", _("Delivered")),
        ("cancelled", _("Cancelled")),
    ]
    APPROVAL_STATUS_CHOICES = [
        ("not_required", _("Not required")),
        ("awaiting_customer", _("Awaiting customer approval")),
        ("pending", _("Waiting for reception decision")),
        ("approved", _("Approved")),
        ("rejected", _("Rejected")),
    ]
    WAREHOUSE_ETA_KIND_CHOICES = [
        ("stock", _("Available in stock")),
        ("supplier", _("To order from supplier")),
    ]
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="parts_requests")
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.CASCADE, related_name="parts_requests")
    job = models.ForeignKey("orders.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests")
    part = models.ForeignKey("parts.Part", on_delete=models.SET_NULL, null=True, blank=True, related_name="requests")
    supplier_offer = models.ForeignKey("parts.PartSupplierOffer", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests", verbose_name="Offerta fornitore")
    custom_item = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=30, default="each")
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_delivered = models.CharField(max_length=30, blank=True)
    quantity_delivered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conversion_factor = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    repair_minutes = models.PositiveIntegerField(default=0)
    customer_quoted_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Customer quoted total"),
    )
    invoice_unit_price_override = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Prezzo unitario fatturato",
    )
    approval_status = models.CharField(
        max_length=25,
        choices=APPROVAL_STATUS_CHOICES,
        default="not_required",
        verbose_name=_("Customer approval"),
    )
    customer_approval_recorded_at = models.DateTimeField(null=True, blank=True)
    customer_approval_recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_approvals_recorded",
    )
    approval_decided_at = models.DateTimeField(null=True, blank=True)
    approval_decided_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parts_approvals_decided",
    )
    notes = models.TextField(blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Prezzo d'acquisto concordato")
    order_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="new")
    warranty_claim = models.ForeignKey("orders.WarrantyClaim", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests")
    authorization = models.TextField(blank=True)
    documents = models.JSONField(default=list, blank=True)
    defect_photos = models.JSONField(default=list, blank=True)
    defect_description = models.TextField(blank=True)
    requested_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests_created")
    warehouse_eta_kind = models.CharField(max_length=20, choices=WAREHOUSE_ETA_KIND_CHOICES, blank=True)
    warehouse_eta_value = models.PositiveIntegerField(null=True, blank=True)
    warehouse_eta_updated_at = models.DateTimeField(null=True, blank=True)
    warehouse_eta_updated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="warehouse_estimates_recorded",
    )
    warehouse_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    warehouse_reminder_answered_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivered_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="parts_requests_delivered")
    inventory_applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"RO {self.work_order.ro_number} · {self.part or self.custom_item}"

    @property
    def warehouse_reminder_pending(self):
        return bool(
            self.warehouse_reminder_sent_at
            and (
                self.warehouse_reminder_answered_at is None
                or self.warehouse_reminder_answered_at < self.warehouse_reminder_sent_at
            )
        )

    def clean(self):
        super().clean()
        if self.supplier_offer_id:
            offer = self.supplier_offer
            if offer.part_id != self.part_id or (self.workshop_id and offer.part.workshop_id != self.workshop_id):
                raise ValidationError({"supplier_offer": "Scegli un’offerta associata a questo ricambio e alla stessa officina."})


class JobPartUsage(models.Model):
    """Inventory parts consumed by a mechanic during a job session."""
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="job_part_usages")
    job = models.ForeignKey("orders.Job", on_delete=models.CASCADE, related_name="parts_used")
    part = models.ForeignKey("parts.Part", on_delete=models.PROTECT, related_name="job_usages")
    quantity_used = models.DecimalField(max_digits=12, decimal_places=2)
    invoice_unit_price_override = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Prezzo unitario fatturato",
    )
    used_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="job_parts_used")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_used__gt=0),
                name="job_part_usage_quantity_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.invoice_unit_price_override is not None and self.invoice_unit_price_override < 0:
            raise ValidationError({"invoice_unit_price_override": "Il prezzo non può essere negativo."})
        if self.part_id and self.workshop_id and self.part.workshop_id != self.workshop_id:
            raise ValidationError({"part": "Il ricambio deve appartenere alla stessa officina."})
        if self.job_id and self.workshop_id and self.job.workshop_id != self.workshop_id:
            raise ValidationError({"job": "La lavorazione deve appartenere alla stessa officina."})
        if self.quantity_used <= 0:
            raise ValidationError({"quantity_used": "La quantità deve essere maggiore di zero."})


class WarehouseNote(models.Model):
    """Comunicazione del magazzino al meccanico su un ricambio non disponibile."""
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="warehouse_notes")
    work_order = models.ForeignKey("orders.WorkOrder", on_delete=models.CASCADE, related_name="warehouse_notes")
    parts_request = models.ForeignKey(
        "parts.PartsRequest", on_delete=models.CASCADE, null=True, blank=True,
        related_name="warehouse_notes",
    )
    part = models.ForeignKey(
        "parts.Part", on_delete=models.SET_NULL, null=True, blank=True, related_name="warehouse_notes",
    )
    author = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="warehouse_notes_created",
    )
    text = models.TextField(verbose_name="Nota")
    estimated_delivery_at = models.DateField(
        null=True, blank=True, verbose_name="Data prevista di consegna",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [
            models.Index(fields=("workshop", "work_order", "created_at"), name="warehouse_note_order_idx"),
        ]
        verbose_name = "Nota del magazzino"
        verbose_name_plural = "Note del magazzino"

    def clean(self):
        super().clean()
        if self.work_order_id and self.workshop_id and self.work_order.workshop_id != self.workshop_id:
            raise ValidationError({"work_order": "L'ordine deve appartenere alla stessa officina."})
        if self.parts_request_id and self.work_order_id:
            if self.parts_request.work_order_id != self.work_order_id:
                raise ValidationError({"parts_request": "La richiesta deve appartenere all'ordine indicato."})
        if self.part_id and self.workshop_id and self.part.workshop_id != self.workshop_id:
            raise ValidationError({"part": "Il ricambio deve appartenere alla stessa officina."})

    def __str__(self):
        return f"Nota magazzino · RO {self.work_order.ro_number}"


class WarehouseNoteRead(models.Model):
    note = models.ForeignKey(WarehouseNote, on_delete=models.CASCADE, related_name="read_receipts")
    recipient = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="warehouse_note_reads",
    )
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Letta il")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("note", "recipient"), name="unique_warehouse_note_recipient"),
        ]
        indexes = [
            models.Index(fields=("recipient", "read_at"), name="warehouse_note_unread_idx"),
        ]
        verbose_name = "Lettura nota magazzino"
        verbose_name_plural = "Letture note magazzino"
