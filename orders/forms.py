from decimal import Decimal

from django import forms
from django.forms import BaseFormSet, formset_factory, inlineformset_factory
from django.utils.translation import gettext_lazy as _

from clientandsuppliers.models import CamperOwner
from parts.models import ArticleClass, ArticleGroup, Part
from .models import (
    BillOfMaterials,
    BillOfMaterialsLine,
    CustomerItemDiscount,
    LaborArticle,
    PriceList,
    PriceListItem,
)


def _validate_price_dates(form, cleaned):
    slots = (
        ("previous_price", "previous_valid_from"),
        ("unit_price", "valid_from"),
        ("future_price", "future_valid_from"),
    )
    for price_field, date_field in slots:
        if (cleaned.get(price_field) is not None) != (cleaned.get(date_field) is not None):
            form.add_error(date_field, _("Enter both a price and its start date."))
    previous_date = cleaned.get("previous_valid_from")
    current_date = cleaned.get("valid_from")
    future_date = cleaned.get("future_valid_from")
    if previous_date and current_date and previous_date >= current_date:
        form.add_error("previous_valid_from", _("The previous price must start before the current price."))
    if current_date and future_date and future_date <= current_date:
        form.add_error("future_valid_from", _("The future price must start after the current price."))


class CustomerCodeChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, customer):
        return f"{customer.customer_code} · {customer}"


class PriceListForm(forms.ModelForm):
    class Meta:
        model = PriceList
        fields = ("code", "name", "customer", "current_valid_from", "future_valid_from", "is_active")
        widgets = {
            "current_valid_from": forms.DateInput(attrs={"type": "date"}),
            "future_valid_from": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, workshop, customer=None, **kwargs):
        super().__init__(*args, **kwargs)
        if customer is not None:
            self.fields.pop("customer", None)
            self.fields.pop("code", None)
        else:
            self.fields["customer"] = CustomerCodeChoiceField(
                queryset=CamperOwner.objects.filter(workshop=workshop, kind__in=("customer", "both")),
                required=False,
                label=_("Customer code association"),
                empty_label=_("Generic price list"),
            )
            if not self.instance.pk:
                self.fields["customer"].required = True

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        if customer:
            cleaned["code"] = customer.customer_code
        return cleaned


class PriceListItemForm(forms.ModelForm):
    class Meta:
        model = PriceListItem
        fields = (
            "part", "labor_article", "article_class", "article_group",
            "previous_price", "previous_valid_from", "unit_price", "valid_from",
            "future_price", "future_valid_from",
        )
        widgets = {
            "previous_valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "future_valid_from": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["part"].queryset = Part.objects.filter(workshop=workshop)
        self.fields["labor_article"].queryset = LaborArticle.objects.filter(
            workshop=workshop, is_active=True
        )
        self.fields["article_class"].queryset = ArticleClass.objects.filter(
            workshop=workshop, is_active=True
        )
        self.fields["article_group"].queryset = ArticleGroup.objects.filter(
            workshop=workshop, is_active=True
        )

    def clean(self):
        cleaned = super().clean()
        targets = [
            cleaned.get("part"),
            cleaned.get("labor_article"),
            cleaned.get("article_class"),
            cleaned.get("article_group"),
        ]
        if sum(1 for t in targets if t) != 1:
            self.add_error(
                None,
                _("Choose exactly one part, labor article, article class or article group."),
            )
        _validate_price_dates(self, cleaned)
        return cleaned

PriceListItemFormSet = inlineformset_factory(
    PriceList, PriceListItem, form=PriceListItemForm, extra=5, can_delete=True,
)


class LaborArticleListEntryForm(forms.ModelForm):
    unit_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        label=_("Current price"),
    )
    valid_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label=_("Current price valid from"),
    )
    previous_price = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, label=_("Previous price"),
    )
    previous_valid_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False, label=_("Previous price valid from"),
    )
    future_price = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"),
        required=False, label=_("Future price"),
    )
    future_valid_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False, label=_("Future price valid from"),
    )

    class Meta:
        model = LaborArticle
        fields = (
            "code", "description", "tariff_type", "previous_price", "previous_valid_from",
            "unit_price", "valid_from", "future_price", "future_valid_from",
        )

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.workshop = workshop
        self.fields["tariff_type"].initial = None

    def clean(self):
        cleaned = super().clean()
        _validate_price_dates(self, cleaned)
        return cleaned

    def clean_code(self):
        code = self.cleaned_data["code"]
        articles = LaborArticle.objects.filter(workshop=self.workshop, code=code)
        if self.instance.pk:
            articles = articles.exclude(pk=self.instance.pk)
        if articles.exists():
            raise forms.ValidationError(_("This labor code already exists; add it from the list entries."))
        return code


class LaborArticleListEntryBaseFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        codes = set()
        for form in self.forms:
            if not form.cleaned_data or not form.has_changed():
                continue
            code = form.cleaned_data.get("code")
            if code and code in codes:
                form.add_error("code", _("Enter each labor code only once."))
            elif code:
                codes.add(code)


LaborArticleListEntryFormSet = formset_factory(
    LaborArticleListEntryForm, formset=LaborArticleListEntryBaseFormSet, extra=2,
)


class CustomerItemDiscountForm(forms.ModelForm):
    class Meta:
        model = CustomerItemDiscount
        exclude = ("customer",)

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["part"].queryset = Part.objects.filter(workshop=workshop)
        self.fields["labor_article"].queryset = LaborArticle.objects.filter(
            workshop=workshop, is_active=True
        )
        self.fields["article_class"].queryset = ArticleClass.objects.filter(
            workshop=workshop, is_active=True
        )
        self.fields["article_group"].queryset = ArticleGroup.objects.filter(
            workshop=workshop, is_active=True
        )
        self.fields["part"].required = False
        self.fields["labor_article"].required = False
        self.fields["article_class"].required = False
        self.fields["article_group"].required = False

    def clean_discount_percent(self):
        value = self.cleaned_data["discount_percent"]
        if not 0 <= value <= 100:
            raise forms.ValidationError(_("The discount must be between 0 and 100%."))
        return value

    def clean(self):
        cleaned = super().clean()
        targets = [
            cleaned.get("part"),
            cleaned.get("labor_article"),
            cleaned.get("article_class"),
            cleaned.get("article_group"),
        ]
        if sum(1 for t in targets if t) != 1:
            self.add_error(
                None,
                _("Choose exactly one part, labor article, article class or article group."),
            )
        return cleaned


CustomerItemDiscountFormSet = inlineformset_factory(
    CamperOwner, CustomerItemDiscount, form=CustomerItemDiscountForm, extra=3, can_delete=True,
)


class BillOfMaterialsForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterials
        fields = ("code", "name", "description", "is_active")


class BillOfMaterialsLineForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterialsLine
        fields = ("sequence", "title", "description", "department", "specialty", "labor_article", "standard_minutes")

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        if "labor_article" in self.fields:
            self.fields["labor_article"].queryset = LaborArticle.objects.filter(
                workshop=workshop,
                is_active=True,
            ).order_by("code")


BillOfMaterialsLineFormSet = inlineformset_factory(
    BillOfMaterials,
    BillOfMaterialsLine,
    form=BillOfMaterialsLineForm,
    extra=1,
    can_delete=True,
)
