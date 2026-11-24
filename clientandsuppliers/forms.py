from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import CamperOwner, ContactDocument
from orders.models import PriceList


class PriceListChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, price_list):
        customer_code = price_list.customer.customer_code if price_list.customer_id else ""
        label = f"{customer_code} · " if customer_code else ""
        return f"{label}{price_list.code} · {price_list.name}"


class ClientSupplierForm(forms.ModelForm):
    class Meta:
        model = CamperOwner
        exclude = ("workshop", "created_at")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.workshop = workshop
        price_lists = PriceList.objects.filter(workshop=workshop, is_active=True)
        if self.instance.pk:
            price_lists = price_lists.filter(Q(customer__isnull=True) | Q(customer=self.instance))
        else:
            price_lists = price_lists.filter(customer__isnull=True)
        self.fields["price_list"] = PriceListChoiceField(
            queryset=price_lists.select_related("customer"),
            required=False,
            label=_("Price list"),
            empty_label=_("Use the CLIENTE price list"),
        )
        if not self.is_bound and self.instance.is_customer and not self.instance.price_list_id:
            default_list = PriceList.objects.filter(
                workshop=workshop, is_default=True, is_active=True,
            ).first()
            if default_list:
                self.initial["price_list"] = default_list
        if self.instance.pk and not self.instance.is_customer:
            self.fields.pop("price_list")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") not in ("customer", "both"):
            cleaned["price_list"] = None
        elif not cleaned.get("price_list"):
            default_list = PriceList.objects.filter(
                workshop=self.workshop, is_default=True, is_active=True,
            ).first()
            if default_list:
                cleaned["price_list"] = default_list
            else:
                self.add_error("price_list", _("The CLIENTE price list is not configured for this workshop."))
        return cleaned


class ContactDocumentForm(forms.ModelForm):
    class Meta:
        model = ContactDocument
        fields = ("category", "file", "caption")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.fields["category"].queryset.filter(is_active=True)
