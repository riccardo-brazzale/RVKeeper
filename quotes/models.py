from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class Quote(models.Model):
    STATUS_CHOICES = [
        ("draft", "Bozza"), ("sent", "Inviato"), ("approved", "Accettato"),
        ("rejected", "Rifiutato"), ("expired", "Scaduto"),
    ]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="quotes")
    quote_number = models.CharField(max_length=40, verbose_name="Numero preventivo")
    customer = models.ForeignKey("fleet.CamperOwner", on_delete=models.PROTECT, related_name="quotes")
    vehicle = models.ForeignKey("fleet.Camper", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes")
    work_order = models.OneToOneField("fleet.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="source_quote")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    description = models.TextField(blank=True, verbose_name="Richiesta / diagnosi")
    notes = models.TextField(blank=True, verbose_name="Note per il cliente")
    valid_until = models.DateField(null=True, blank=True, verbose_name="Valido fino al")
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="quotes_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "fleet"
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("workshop", "quote_number"), name="unique_quote_number_per_workshop")]
        verbose_name = "Preventivo"
        verbose_name_plural = "Preventivi"

    def clean(self):
        super().clean()
        if self.customer_id and ((self.workshop_id and self.customer.workshop_id != self.workshop_id) or not self.customer.is_customer):
            raise ValidationError({"customer": "Seleziona un cliente della stessa officina."})
        if self.vehicle_id and self.workshop_id and self.vehicle.workshop_id != self.workshop_id:
            raise ValidationError({"vehicle": "Seleziona un veicolo della stessa officina."})
        if self.customer_id and self.vehicle_id and self.vehicle.owner_id and self.vehicle.owner_id != self.customer_id:
            raise ValidationError({"vehicle": "Il veicolo deve appartenere al cliente selezionato."})

    @property
    def subtotal(self):
        return sum((line.subtotal for line in self.lines.all()), Decimal("0.00"))

    @property
    def total(self):
        return sum((line.total for line in self.lines.all()), Decimal("0.00"))

    def __str__(self):
        return f"Preventivo {self.quote_number} · {self.customer}"


class QuoteLine(models.Model):
    TYPES = [("part", "Ricambio"), ("labor", "Manodopera"), ("other", "Altro")]
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    line_type = models.CharField(max_length=10, choices=TYPES, default="labor", verbose_name="Tipo riga")
    part = models.ForeignKey("fleet.Part", on_delete=models.SET_NULL, null=True, blank=True, related_name="quote_lines")
    description = models.CharField(max_length=250, verbose_name="Descrizione")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=30, default="pz")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Prezzo unitario")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Sconto (%)")
    standard_minutes = models.PositiveIntegerField(default=0, verbose_name="Tempo standard (minuti)")

    class Meta:
        app_label = "fleet"
        ordering = ("pk",)

    def clean(self):
        super().clean()
        if not self.description.strip():
            raise ValidationError({"description": "La descrizione è obbligatoria."})
        if self.quantity <= 0:
            raise ValidationError({"quantity": "La quantità deve essere maggiore di zero."})
        if self.unit_price < 0:
            raise ValidationError({"unit_price": "Il prezzo non può essere negativo."})
        if self.discount_percent < 0 or self.discount_percent > 100:
            raise ValidationError({"discount_percent": "Lo sconto deve essere compreso tra 0 e 100%."})
        if self.part_id and self.quote_id and self.quote.workshop_id != self.part.workshop_id:
            raise ValidationError({"part": "Il ricambio deve appartenere alla stessa officina del preventivo."})

    @property
    def subtotal(self):
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    @property
    def total(self):
        return (self.subtotal * (1 - self.discount_percent / 100)).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.description} · {self.quantity} {self.unit}"
