from django import forms

from clientandsuppliers.models import CamperOwner
from django.forms import inlineformset_factory

from .models import (
    ArticleClass,
    ArticleGroup,
    Part,
    PartDocument,
    PartSupplierOffer,
    PurchaseOrder,
    PurchaseOrderLine,
)


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        exclude = ("workshop", "cost_price", "quantity", "standard_minutes", "created_at", "updated_at")

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["article_class"].queryset = ArticleClass.objects.filter(
            workshop=workshop, is_active=True
        )
        self.fields["article_group"].queryset = ArticleGroup.objects.filter(
            workshop=workshop, is_active=True
        )
        # Se esiste già una classe generica per l'officina, preselezionala
        if not self.is_bound and not self.instance.pk:
            default_class = ArticleClass.objects.filter(
                workshop=workshop, code="GENERIC"
            ).first()
            if default_class:
                self.initial["article_class"] = default_class.pk
                default_group = ArticleGroup.objects.filter(
                    workshop=workshop, article_class=default_class, code="VARIE"
                ).first()
                if default_group:
                    self.initial["article_group"] = default_group.pk



class PartSupplierOfferForm(forms.ModelForm):
    class Meta:
        model = PartSupplierOffer
        exclude = ("part", "updated_at")

    def __init__(self, *args, workshop, part, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.part = part
        self.fields["supplier"].queryset = CamperOwner.objects.filter(workshop=workshop, kind__in=("supplier", "both"))


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ("supplier", "order_date", "notes")

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = CamperOwner.objects.filter(
            workshop=workshop,
            kind__in=("supplier", "both"),
        )


class PurchaseOrderLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = (
            "part",
            "quantity_required",
            "quantity_ordered",
            "unit_price",
            "discount_percent",
        )

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["part"].queryset = Part.objects.filter(workshop=workshop).order_by(
            "part_number",
            "name",
        )


PurchaseOrderLineFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    extra=5,
    can_delete=True,
)


class PartDocumentForm(forms.ModelForm):
    class Meta:
        model = PartDocument
        fields = ("category", "file", "caption")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.fields["category"].queryset.filter(is_active=True)
