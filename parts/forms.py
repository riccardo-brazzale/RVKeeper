from decimal import Decimal

from django import forms

from clientandsuppliers.models import CamperOwner
from .models import ArticleClass, ArticleGroup, Part, PartDocument, PartSupplierOffer


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        exclude = ("workshop", "quantity", "created_at", "updated_at")

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


class PartPricesForm(forms.Form):
    def __init__(self, *args, price_lists, price_items, **kwargs):
        super().__init__(*args, **kwargs)
        self.price_lists = list(price_lists)
        self.field_names = {}
        for price_list in self.price_lists:
            item = price_items.get(price_list.pk)
            names = {}
            for slot, price_attr, date_attr, required in (
                ("previous", "previous_price", "previous_valid_from", False),
                ("current", "unit_price", "valid_from", price_list.is_default),
                ("future", "future_price", "future_valid_from", False),
            ):
                price_name = f"price_{price_list.pk}_{slot}"
                date_name = f"valid_from_{price_list.pk}_{slot}"
                self.fields[price_name] = forms.DecimalField(
                    label="", required=required, max_digits=12,
                    decimal_places=2, min_value=Decimal("0"),
                )
                self.fields[date_name] = forms.DateField(
                    label="", required=False,
                    widget=forms.DateInput(attrs={"type": "date"}),
                )
                if item is not None:
                    self.initial[price_name] = getattr(item, price_attr)
                    self.initial[date_name] = getattr(item, date_attr)
                names[slot] = {"price": price_name, "date": date_name}
            self.field_names[price_list.pk] = names

    def clean(self):
        cleaned = super().clean()
        for price_list in self.price_lists:
            names = self.field_names[price_list.pk]
            for slot_names in names.values():
                price = cleaned.get(slot_names["price"])
                valid_from = cleaned.get(slot_names["date"])
                if (price is not None) != (valid_from is not None):
                    self.add_error(slot_names["date"], _("Enter both a price and its start date."))
            previous_date = cleaned.get(names["previous"]["date"])
            current_price = cleaned.get(names["current"]["price"])
            current_date = cleaned.get(names["current"]["date"])
            future_date = cleaned.get(names["future"]["date"])
            previous_price = cleaned.get(names["previous"]["price"])
            future_price = cleaned.get(names["future"]["price"])
            if (previous_price is not None or future_price is not None) and current_price is None:
                self.add_error(names["current"]["price"], _("A current price is required when other periods are set."))
            if previous_date and current_date and previous_date >= current_date:
                self.add_error(names["previous"]["date"], _("The previous price must start before the current price."))
            if current_date and future_date and future_date <= current_date:
                self.add_error(names["future"]["date"], _("The future price must start after the current price."))
        return cleaned


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
        fields = ("category", "file", "caption")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.fields["category"].queryset.filter(is_active=True)
