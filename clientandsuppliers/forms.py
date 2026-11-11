from django import forms

from .models import CamperOwner, ContactDocument


class ClientSupplierForm(forms.ModelForm):
    class Meta:
        model = CamperOwner
        exclude = ("workshop", "created_at")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}


class ContactDocumentForm(forms.ModelForm):
    class Meta:
        model = ContactDocument
        fields = ("category", "file", "caption")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.fields["category"].queryset.filter(is_active=True)
