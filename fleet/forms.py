from django import forms

from .models import Camper, CamperOwner


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
        self.fields["owner"].queryset = CamperOwner.objects.filter(workshop=workshop)
