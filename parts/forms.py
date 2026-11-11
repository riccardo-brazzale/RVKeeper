from django import forms

from clientandsuppliers.models import CamperOwner
from .models import Part, PartDocument, PartSupplierOffer


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        exclude = ("workshop", "quantity", "created_at", "updated_at")


class PartSupplierOfferForm(forms.ModelForm):
    class Meta:
        model = PartSupplierOffer
        exclude = ("part", "updated_at")

    def __init__(self, *args, workshop, part, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.part = part
        self.fields["supplier"].queryset = CamperOwner.objects.filter(workshop=workshop, kind__in=("supplier", "both"))


class PartDocumentForm(forms.ModelForm):
    class Meta:
        model = PartDocument
        fields = ("document_type", "file", "caption")
