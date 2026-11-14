from django import forms
from django.forms import inlineformset_factory

from clientandsuppliers.models import CamperOwner
from fleet.models import Camper
from parts.models import Part
from .models import Quote, QuoteLine


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        exclude = ("workshop", "quote_number", "work_order", "status", "created_by", "created_at", "updated_at")
        widgets = {"valid_until": forms.DateInput(attrs={"type": "date"}), "description": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = CamperOwner.objects.filter(workshop=workshop, kind__in=("customer", "both"))
        self.fields["vehicle"].queryset = Camper.objects.filter(
            workshop=workshop,
            is_active=True,
            owner__kind__in=("customer", "both"),
        ).select_related("owner")
        self.fields["vehicle"].required = False


class QuoteLineForm(forms.ModelForm):
    class Meta:
        model = QuoteLine
        exclude = ("quote",)

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["part"].queryset = Part.objects.filter(workshop=workshop)
        self.fields["part"].required = False
        self.fields["description"].required = False

    def clean(self):
        cleaned = super().clean()
        part = cleaned.get("part")
        description = cleaned.get("description", "").strip()
        if not description and part:
            cleaned["description"] = part.name
        elif not description and not cleaned.get("DELETE"):
            self.add_error("description", "Inserisci una descrizione per la voce.")
        return cleaned


QuoteLineFormSet = inlineformset_factory(
    Quote, QuoteLine, form=QuoteLineForm, extra=5, can_delete=True, min_num=1, validate_min=True,
)
