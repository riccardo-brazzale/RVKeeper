from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import BaseFormSet, formset_factory, modelformset_factory
from django.utils.translation import gettext_lazy as _

from clientandsuppliers.models import CamperOwner
from orders.models import BillOfMaterials, Job, WorkOrder
from .models import Camper, CamperPhoto
from parts.forms import PartDocumentForm, PartSupplierOfferForm
from parts.models import JobPartUsage, Part, PartsRequest


class CustomerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, contact):
        return f"{contact.customer_code} · {contact}" if contact.customer_code else str(contact)


class TechnicianChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        return user.get_full_name() or user.username


class TimeReportFilterForm(forms.Form):
    technician = TechnicianChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label=_("Technician"),
        empty_label=_("All technicians"),
    )
    date_from = forms.DateField(
        label=_("From"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label=_("To"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bom_template"] = forms.ModelChoiceField(
            queryset=BillOfMaterials.objects.filter(workshop=workshop, is_active=True),
            required=False,
            label=_("Distinta base"),
            help_text=_("Alla creazione aggiunge automaticamente tutte le attività previste."),
        )
        user_model = get_user_model()
        self.fields["technician"].queryset = (
            user_model.objects.filter(profile="mechanic")
            .filter(
                Q(memberships__workshop=workshop, memberships__is_active=True)
                | Q(time_events__workshop=workshop)
            )
            .distinct()
            .order_by("first_name", "last_name", "username")
        )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("date_from")
        end = cleaned_data.get("date_to")
        if start and end and start > end:
            self.add_error("date_to", _("The end date must be on or after the start date."))
        return cleaned_data


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
        owner_queryset = CamperOwner.objects.filter(workshop=workshop, kind__in=("customer", "both"))
        self.fields["owner"] = CustomerChoiceField(
            queryset=owner_queryset,
            required=True,
            label=self.fields["owner"].label,
        )
        self.fields["owner"].required = True


class CamperSelect(forms.Select):
    def __init__(self, *args, campers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.camper_map = {str(camper.pk): camper for camper in campers}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        camper = self.camper_map.get(str(value))
        if camper:
            owner = camper.owner
            values = {
                "internal-number": camper.internal_number,
                "plate": camper.plate,
                "vin": camper.vin,
                "owner": f"{owner.customer_code} · {owner}" if owner and owner.customer_code else str(owner) if owner else "",
                "owner-phone": owner.phone if owner else "",
                "owner-email": owner.email if owner else "",
                "brand": camper.brand,
                "model": camper.model,
                "year": camper.registration_date.year if camper.registration_date else "",
                "registration-date": camper.registration_date.isoformat() if camper.registration_date else "",
                "engine": " ".join(value for value in (camper.engine_brand, camper.engine_model) if value),
                "engine-details": " · ".join(str(value) for value in (
                    f"{camper.engine_displacement} cc" if camper.engine_displacement else "",
                    f"{camper.engine_power} kW" if camper.engine_power else "",
                ) if value),
                "fuel": camper.get_fuel_type_display(),
                "transmission": camper.get_transmission_display(),
                "body": " ".join(value for value in (camper.body_brand, camper.body_model) if value),
                "seats": camper.seats,
                "sleeping-places": camper.sleeping_places,
                "dimensions": " × ".join(str(value) for value in (camper.length_mm, camper.width_mm, camper.height_mm) if value) + (" mm" if any((camper.length_mm, camper.width_mm, camper.height_mm)) else ""),
                "weights": " / ".join(str(value) for value in (camper.tare_weight, camper.max_weight) if value) + (" kg" if any((camper.tare_weight, camper.max_weight)) else ""),
                "mileage": camper.mileage,
                "mileage-updated": camper.mileage_updated_at,
                "notes": camper.notes,
                "active": str(_("Active") if camper.is_active else _("Inactive")),
            }
            option["attrs"].update({f"data-{key}": str(value or "") for key, value in values.items()})
        return option


class CamperChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, camper):
        owner = camper.owner
        owner_label = f"{owner.customer_code} · {owner}" if owner and owner.customer_code else str(owner or "")
        return f"{camper} · {owner_label}"


class LineListField(forms.CharField):
    """Present a JSON list as ordinary one-item-per-line text."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("widget", forms.Textarea(attrs={"rows": 5}))
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        if value is None or value == "":
            return ""
        if isinstance(value, (list, tuple)):
            return "\n".join(str(item) for item in value)
        if isinstance(value, dict):
            return "\n".join(f"{key}: {item}" for key, item in value.items())
        return str(value)

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return []
        return [line.strip() for line in value.splitlines() if line.strip()]


class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        exclude = (
            "workshop", "customer", "customer_name", "customer_phone", "customer_email", "ro_number",
            "status", "created_by", "completed_at", "invoiced", "invoiced_at",
            "invoiced_by", "created_at", "updated_at",
        )
        labels = {
            "vehicle": _("Vehicle / camper"),
            "year": _("Year"),
            "make": _("Make"),
            "model": _("Model"),
            "odometer": _("Odometer"),
            "work_classification": _("Work classification"),
            "warranty_status": _("Warranty status"),
            "reception_notes": _("Reception notes"),
            "checklist": _("Checklist"),
            "damages": _("Damages"),
        }

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_vehicle_id = self.instance.vehicle_id if self.instance.pk else None
        self.original_snapshots = {
            name: getattr(self.instance, name)
            for name in ("year", "make", "model", "odometer")
        }
        camper_queryset = Camper.objects.filter(
                workshop=workshop,
                owner__kind__in=("customer", "both"),
            ).select_related("owner")
        campers = list(camper_queryset)
        self.fields["vehicle"] = CamperChoiceField(
            queryset=camper_queryset,
            required=True,
            label=_("Vehicle / camper"),
            help_text=_("The customer is automatically taken from the selected camper."),
            widget=CamperSelect(campers=campers),
        )
        for field_name in ("year", "make", "model", "odometer"):
            self.fields[field_name].widget.attrs["readonly"] = True
            self.fields[field_name].widget.attrs["data-camper-snapshot"] = field_name
        for field_name, help_text in (
            ("checklist", _("Enter one item per line.")),
            ("damages", _("Enter one damage per line.")),
        ):
            original = self.fields[field_name]
            self.fields[field_name] = LineListField(
                label=original.label,
                help_text=help_text,
                widget=forms.Textarea(attrs={"rows": 5}),
            )

        selected_value = self.initial.get("vehicle")
        selected_camper = selected_value if isinstance(selected_value, Camper) else next(
            (camper for camper in campers if str(camper.pk) == str(selected_value)), None
        )
        if not selected_camper and self.instance.pk:
            selected_camper = next((camper for camper in campers if camper.pk == self.instance.vehicle_id), None)
        if selected_camper:
            self.initial.setdefault("year", selected_camper.registration_date.year if selected_camper.registration_date else "")
            self.initial.setdefault("make", selected_camper.brand)
            self.initial.setdefault("model", selected_camper.model)
            self.initial.setdefault("odometer", selected_camper.mileage)

    def clean_vehicle(self):
        vehicle = self.cleaned_data.get("vehicle")
        if vehicle and (not vehicle.owner_id or not vehicle.owner.is_customer):
            raise forms.ValidationError(_("Select a camper that has a registered customer as its owner."))
        return vehicle

    def clean(self):
        cleaned_data = super().clean()
        vehicle = cleaned_data.get("vehicle")
        if vehicle and vehicle.owner_id:
            self.instance.customer = vehicle.owner
        return cleaned_data

    def save(self, commit=True):
        vehicle = self.cleaned_data["vehicle"]
        vehicle_changed = self.original_vehicle_id != vehicle.pk
        order = super().save(commit=False)
        customer = vehicle.owner
        if vehicle_changed:
            order.customer = customer
            order.customer_name = str(customer)
            order.customer_phone = customer.phone
            order.customer_email = customer.email
            order.year = vehicle.registration_date.year if vehicle.registration_date else ""
            order.make = vehicle.brand
            order.model = vehicle.model
            order.odometer = vehicle.mileage
        else:
            for name, value in self.original_snapshots.items():
                setattr(order, name, value)
        if commit:
            order.save()
            self.save_m2m()
        return order


class CamperPhotoForm(forms.ModelForm):
    class Meta:
        model = CamperPhoto
        fields = ("category", "image", "caption")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.fields["category"].queryset.filter(is_active=True)


class PartChoiceSelect(forms.Select):
    def __init__(self, *args, part_units=None, part_search=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.part_units = part_units or {}
        self.part_search = part_search or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        key = str(value)
        unit = self.part_units.get(key)
        if unit:
            option["attrs"]["data-unit"] = unit
        search_text = self.part_search.get(key)
        if search_text:
            option["attrs"]["data-search"] = search_text
        return option


class PartsRequestLineForm(forms.Form):
    part = forms.ModelChoiceField(queryset=Part.objects.none(), required=False, label=_("Catalog part"))
    quantity_requested = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False, label=_("Quantity")
    )
    notes = forms.CharField(required=False, label=_("Notes"), widget=forms.TextInput())

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        parts = Part.objects.filter(workshop=workshop)
        self.fields["part"].queryset = parts
        part_widget = PartChoiceSelect(
            attrs={"data-part-select": ""},
            part_units={str(part.pk): part.unit for part in parts},
            part_search={str(part.pk): f"{part.part_number} {part.name}".casefold() for part in parts},
        )
        part_widget.choices = self.fields["part"].choices
        self.fields["part"].widget = part_widget

    def clean(self):
        cleaned_data = super().clean()
        part = cleaned_data.get("part")
        quantity = cleaned_data.get("quantity_requested")
        notes = cleaned_data.get("notes", "").strip()
        if not any((part, quantity, notes)):
            return cleaned_data
        if not part:
            self.add_error("part", _("Choose a catalog part."))
        if quantity is None:
            self.add_error("quantity_requested", _("Enter a quantity greater than zero."))
        return cleaned_data


class NonEmptyPartsRequestFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        has_request = any(
            form.cleaned_data
            and not form.cleaned_data.get("DELETE")
            and form.cleaned_data.get("part")
            for form in self.forms
        )
        if not has_request:
            raise forms.ValidationError(_("Add at least one part before sending the request."))


class PartsUsageLineForm(forms.Form):
    part = forms.ModelChoiceField(queryset=Part.objects.none(), required=False, label=_("Catalog part"))
    quantity_used = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False, label=_("Quantity used")
    )

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        parts = Part.objects.filter(workshop=workshop)
        self.fields["part"].queryset = parts
        part_widget = PartChoiceSelect(
            attrs={"data-part-select": ""},
            part_units={str(part.pk): part.unit for part in parts},
            part_search={str(part.pk): f"{part.part_number} {part.name}".casefold() for part in parts},
        )
        part_widget.choices = self.fields["part"].choices
        self.fields["part"].widget = part_widget

    def clean(self):
        cleaned_data = super().clean()
        part = cleaned_data.get("part")
        quantity = cleaned_data.get("quantity_used")
        if not part and quantity is None:
            return cleaned_data
        if not part:
            self.add_error("part", _("Choose a catalog part."))
        if quantity is None:
            self.add_error("quantity_used", _("Enter a quantity greater than zero."))
        return cleaned_data


PartsRequestFormSet = formset_factory(
    PartsRequestLineForm, formset=NonEmptyPartsRequestFormSet, extra=1, can_delete=True
)
PartsUsageFormSet = formset_factory(PartsUsageLineForm, extra=1, can_delete=True)


class InvoicePartsRequestForm(forms.ModelForm):
    invoice_unit_price_override = forms.DecimalField(
        required=False, max_digits=12, decimal_places=2, min_value=Decimal("0"),
    )

    class Meta:
        model = PartsRequest
        fields = ("invoice_unit_price_override",)
        labels = {"invoice_unit_price_override": _("Unit price")}


class InvoiceLaborPriceForm(forms.ModelForm):
    invoice_hourly_rate_override = forms.DecimalField(
        required=False, max_digits=12, decimal_places=2, min_value=Decimal("0"),
    )

    class Meta:
        model = Job
        fields = ("invoice_hourly_rate_override",)
        labels = {"invoice_hourly_rate_override": _("Hourly rate")}


class InvoiceUsagePriceForm(forms.ModelForm):
    invoice_unit_price_override = forms.DecimalField(
        required=False, max_digits=12, decimal_places=2, min_value=Decimal("0"),
    )

    class Meta:
        model = JobPartUsage
        fields = ("invoice_unit_price_override",)
        labels = {"invoice_unit_price_override": _("Unit price")}


InvoicePartsRequestFormSet = modelformset_factory(
    PartsRequest, form=InvoicePartsRequestForm, extra=0,
)
InvoiceLaborPriceFormSet = modelformset_factory(
    Job, form=InvoiceLaborPriceForm, extra=0,
)
InvoiceUsagePriceFormSet = modelformset_factory(
    JobPartUsage, form=InvoiceUsagePriceForm, extra=0,
)
