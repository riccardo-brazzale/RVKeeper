from django.core.exceptions import ValidationError
from django.db import models


class CamperOwner(models.Model):
    """Contatto commerciale usato come cliente, fornitore o entrambi."""

    KIND_CHOICES = [
        ("customer", "Cliente"),
        ("supplier", "Fornitore"),
        ("both", "Cliente e fornitore"),
    ]

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="camper_owners")
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="customer", verbose_name="Tipo anagrafica")
    is_company = models.BooleanField(default=False, verbose_name="Azienda")
    first_name = models.CharField(max_length=100, blank=True, verbose_name="Nome")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Cognome")
    company_name = models.CharField(max_length=200, blank=True, verbose_name="Ragione sociale")
    tax_code = models.CharField(max_length=30, blank=True, verbose_name="Codice fiscale")
    vat_number = models.CharField(max_length=30, blank=True, verbose_name="Partita IVA")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Telefono")
    email = models.EmailField(blank=True, verbose_name="Email")
    address = models.CharField(max_length=200, blank=True, verbose_name="Indirizzo")
    postal_code = models.CharField(max_length=15, blank=True, verbose_name="CAP")
    city = models.CharField(max_length=100, blank=True, verbose_name="Città")
    country = models.CharField(max_length=2, default="IT", verbose_name="Paese")
    notes = models.TextField(blank=True, verbose_name="Note")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "fleet"
        ordering = ["last_name", "first_name", "company_name"]
        verbose_name = "Contatto commerciale"
        verbose_name_plural = "Clienti e fornitori"

    def clean(self):
        super().clean()
        if self.is_company and not self.company_name.strip():
            raise ValidationError({"company_name": "Inserisci la ragione sociale."})
        if not self.is_company and not (self.first_name.strip() and self.last_name.strip()):
            raise ValidationError({"last_name": "Per un privato sono richiesti nome e cognome."})
        if self.pk and not self.is_customer and (self.campers.exists() or self.work_orders.exists()):
            raise ValidationError({"kind": "Questo contatto è usato da veicoli o ordini e deve restare cliente."})
        if self.pk and not self.is_supplier and self.part_offers.exists():
            raise ValidationError({"kind": "Questo contatto è associato a ricambi e deve restare fornitore."})

    def __str__(self):
        return self.company_name if self.is_company else f"{self.first_name} {self.last_name}".strip()

    @property
    def is_customer(self):
        return self.kind in ("customer", "both")

    @property
    def is_supplier(self):
        return self.kind in ("supplier", "both")


# Compatibilità con gli import storici e con la serializzazione dei dati.
BusinessPartner = CamperOwner
