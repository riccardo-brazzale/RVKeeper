from django import forms

from .models import Camper, CamperOwner, WorkOrder
from parts.forms import PartDocumentForm, PartSupplierOfferForm


class CamperForm(forms.ModelForm):
    class Meta:
        model = Camper
        exclude = ("workshop",)
        widgets = {
            "registration_date": forms.DateInput(attrs={"type": "date"}),
            "mileage_updated_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = CamperOwner.objects.filter(workshop=workshop, kind__in=("customer", "both"))
        self.fields["owner"].required = True


class CustomerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, customer):
        label = str(customer)
        if customer.phone:
            label = f"{label} · {customer.phone}"
        return label


class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        exclude = (
            "workshop", "customer_name", "customer_phone", "customer_email",
            "status", "created_by", "completed_at", "invoiced", "invoiced_at",
            "invoiced_by", "created_at", "updated_at",
        )
        labels = {"customer": "Cliente da anagrafica"}

    def __init__(self, *args, workshop, require_customer=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"] = CustomerChoiceField(
            queryset=CamperOwner.objects.filter(
                workshop=workshop, kind__in=("customer", "both")
            ),
            required=require_customer or bool(self.instance.customer_id),
            label="Cliente da anagrafica",
            help_text="Nome e telefono dell’ordine vengono sincronizzati dalla scheda cliente.",
        )
        self.fields["vehicle"].queryset = Camper.objects.filter(workshop=workshop)
