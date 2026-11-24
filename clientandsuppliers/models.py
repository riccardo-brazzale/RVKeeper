from django.core.exceptions import ValidationError
from django.db import models


def contact_document_path(instance, filename):
    import os
    from django.utils.text import slugify
    contact = instance.contact
    label = contact.company_name if contact.is_company else f"{contact.last_name}-{contact.first_name}"
    key = slugify(label) or f"contact-{contact.pk}"
    return f"contacts/{key}/{instance.category.code}/{os.path.basename(filename)}"


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
    price_list = models.ForeignKey(
        "orders.PriceList", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="customers", verbose_name="Listino generale assegnato",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
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
        if self.price_list_id:
            if not self.is_customer:
                raise ValidationError({"price_list": "Solo un cliente può avere un listino assegnato."})
            if self.workshop_id and self.price_list.workshop_id != self.workshop_id:
                raise ValidationError({"price_list": "Il listino deve appartenere alla stessa officina."})
            if self.price_list.customer_id and self.price_list.customer_id != self.pk:
                raise ValidationError({"price_list": "Il listino cliente è riservato al cliente associato."})

    def save(self, *args, **kwargs):
        if self.is_customer and not self.price_list_id and self.workshop_id:
            from orders.models import PriceList

            default_list = PriceList.objects.filter(
                workshop_id=self.workshop_id, is_default=True, is_active=True,
            ).first()
            if default_list is None:
                raise ValidationError({"price_list": "L'officina non ha un listino CLIENTE attivo."})
            self.price_list = default_list
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "price_list"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.company_name if self.is_company else f"{self.first_name} {self.last_name}".strip()

    @property
    def customer_code(self):
        return f"CLI-{self.pk:06d}" if self.pk and self.is_customer else ""

    @property
    def supplier_code(self):
        return f"FOR-{self.pk:06d}" if self.pk and self.is_supplier else ""

    @property
    def is_customer(self):
        return self.kind in ("customer", "both")

    @property
    def is_supplier(self):
        return self.kind in ("supplier", "both")


class ContactDocument(models.Model):
    contact = models.ForeignKey(CamperOwner, on_delete=models.CASCADE, related_name="documents")
    category = models.ForeignKey("orders.DocumentCategory", on_delete=models.PROTECT, related_name="contact_documents")
    file = models.FileField(upload_to=contact_document_path)
    caption = models.CharField(max_length=250, blank=True)
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.caption or self.file.name


# Compatibilità con gli import storici e con la serializzazione dei dati.
