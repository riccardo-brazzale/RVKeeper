from django import forms
from django.forms import inlineformset_factory

from clientandsuppliers.models import CamperOwner
from fleet.forms import PartChoiceSelect
from fleet.models import Camper
from orders.models import LaborArticle
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
        parts = Part.objects.filter(workshop=workshop)
        self.fields["part"].queryset = parts
        self.fields["labor_article"].queryset = LaborArticle.objects.filter(workshop=workshop, is_active=True)
        self.fields["part"].required = False
        self.fields["description"].required = False
        part_widget = PartChoiceSelect(
            attrs={"data-part-select": ""},
            part_units={str(part.pk): part.unit for part in parts},
            part_search={str(part.pk): f"{part.part_number} {part.name}".casefold() for part in parts},
        )
        part_widget.choices = self.fields["part"].choices
        self.fields["part"].widget = part_widget

    def clean(self):
        cleaned = super().clean()
        part = cleaned.get("part")
        labor_article = cleaned.get("labor_article")
        description = cleaned.get("description", "").strip()
        if part and labor_article:
            self.add_error("labor_article", "Scegli un ricambio o un articolo di manodopera, non entrambi.")
        if not description and part:
            cleaned["description"] = part.name
        elif not description and labor_article:
            cleaned["description"] = labor_article.description
        elif not description and not cleaned.get("DELETE"):
            self.add_error("description", "Inserisci una descrizione per la voce.")
        return cleaned


QuoteLineFormSet = inlineformset_factory(
    Quote, QuoteLine, form=QuoteLineForm, extra=5, can_delete=True, min_num=1, validate_min=True,
)
