from django import forms
from django.utils.translation import gettext_lazy as _

from clientandsuppliers.models import CamperOwner
from orders.models import WorkOrder
from .models import Camper, CamperPhoto
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


class CamperChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, camper):
        return f"{camper} · {camper.owner}"


class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        exclude = (
            "workshop", "customer", "customer_name", "customer_phone", "customer_email",
            "status", "created_by", "completed_at", "invoiced", "invoiced_at",
            "invoiced_by", "created_at", "updated_at",
        )
        labels = {"vehicle": _("Vehicle / camper")}

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"] = CamperChoiceField(
            queryset=Camper.objects.filter(
                workshop=workshop,
                owner__kind__in=("customer", "both"),
            ).select_related("owner"),
            required=True,
            label=_("Vehicle / camper"),
            help_text=_("The customer is automatically taken from the selected camper."),
        )

    def clean_vehicle(self):
        vehicle = self.cleaned_data.get("vehicle")
        if vehicle and (not vehicle.owner_id or not vehicle.owner.is_customer):
            raise forms.ValidationError(_("Select a camper that has a registered customer as its owner."))
        return vehicle

    def clean(self):
        cleaned_data = super().clean()
        vehicle = cleaned_data.get("vehicle")
        if vehicle and vehicle.owner_id:
            self.instance.customer = vehicle.owner
        return cleaned_data

    def save(self, commit=True):
        order = super().save(commit=False)
        customer = self.cleaned_data["vehicle"].owner
        order.customer = customer
        order.customer_name = str(customer)
        order.customer_phone = customer.phone
        order.customer_email = customer.email
        if commit:
            order.save()
            self.save_m2m()
        return order


class CamperPhotoForm(forms.ModelForm):
    class Meta:
        model = CamperPhoto
        fields = ("category", "image", "caption")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.fields["category"].queryset.filter(is_active=True)
