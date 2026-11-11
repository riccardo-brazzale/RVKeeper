from django.core.exceptions import ValidationError
from django.db import models


def part_document_path(instance, filename):
    import os
    from django.utils.text import slugify
    key = slugify(instance.part.part_number) or f"part-{instance.part_id}"
    return f"parts/{key}/{instance.category.code}/{os.path.basename(filename)}"


class Part(models.Model):
    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="parts")
    part_number = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=30, default="pz", verbose_name="Unità di misura")
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Costo unitario")
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Prezzo vendita")
    standard_minutes = models.PositiveIntegerField(default=0, verbose_name="Tempo standard (minuti)")
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


class PartSupplierOffer(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name="supplier_offers")
    supplier = models.ForeignKey("clientandsuppliers.CamperOwner", on_delete=models.PROTECT, related_name="part_offers")
    supplier_code = models.CharField(max_length=100, blank=True, verbose_name="Codice fornitore")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prezzo d'acquisto")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Sconto (%)")
    minimum_order_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name="Quantità minima")
    lead_time_days = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Tempi di consegna (giorni)")
    is_preferred = models.BooleanField(default=False, verbose_name="Fornitore preferito")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("purchase_price", "supplier__company_name", "supplier__last_name")
        constraints = [models.UniqueConstraint(fields=("part", "supplier"), name="unique_supplier_offer_per_part")]

    def clean(self):
        super().clean()
        if self.purchase_price < 0:
            raise ValidationError({"purchase_price": "Il prezzo d'acquisto non può essere negativo."})
        if self.discount_percent < 0 or self.discount_percent > 100:
            raise ValidationError({"discount_percent": "Lo sconto deve essere compreso tra 0 e 100%."})
        if self.minimum_order_quantity <= 0:
            raise ValidationError({"minimum_order_quantity": "La quantità minima deve essere maggiore di zero."})
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


class PartDocument(models.Model):
    part = models.ForeignKey(Part, on_delete=models.CASCADE, related_name="documents")
    category = models.ForeignKey("fleet.DocumentCategory", on_delete=models.PROTECT, related_name="part_documents")
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
