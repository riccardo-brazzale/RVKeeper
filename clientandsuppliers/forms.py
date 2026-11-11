from django import forms

from .models import CamperOwner


class ClientSupplierForm(forms.ModelForm):
    class Meta:
        model = CamperOwner
        exclude = ("workshop", "created_at")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}
