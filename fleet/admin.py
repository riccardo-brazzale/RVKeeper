
from django.contrib import admin
from .models import CamperOwner, Camper, CamperPhoto


@admin.register(CamperOwner)
class CamperOwnerAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "company_name",
        "last_name",
        "first_name",
        "phone",
        "email",
        "workshop",
    )

    list_filter = ("workshop", "is_company")
    search_fields = (
        "first_name",
        "last_name",
        "company_name",
        "tax_code",
        "phone",
        "email",
    )


class CamperPhotoInline(admin.TabularInline):
    model = CamperPhoto
    extra = 1


@admin.register(Camper)
class CamperAdmin(admin.ModelAdmin):

    list_display = (
        "internal_number",
        "plate",
        "brand",
        "model",
        "owner",
        "mileage",
        "workshop",
        "is_active",
    )

    list_filter = (
        "workshop",
        "brand",
        "fuel_type",
        "is_active",
    )

    search_fields = (
        "internal_number",
        "plate",
        "vin",
        "brand",
        "model",
        "owner__last_name",
        "owner__company_name",
    )

    inlines = [CamperPhotoInline]

    fieldsets = (
        ("Identificazione", {
            "fields": (
                "workshop",
                "internal_number",
                "plate",
                "vin",
                "brand",
                "model",
                "registration_date",
                "owner",
                "is_active",
            )
        }),
        ("Motorizzazione", {
            "fields": (
                "engine_brand",
                "engine_model",
                "engine_displacement",
                "engine_power",
                "fuel_type",
                "transmission",
            )
        }),
        ("Allestimento", {
            "fields": (
                "body_brand",
                "body_model",
                "seats",
                "sleeping_places",
            )
        }),
        ("Dimensioni e masse", {
            "fields": (
                "length_mm",
                "width_mm",
                "height_mm",
                "tare_weight",
                "max_weight",
            )
        }),
        ("Manutenzione", {
            "fields": (
                "mileage",
                "mileage_updated_at",
                "notes",
            )
        }),
    )


@admin.register(CamperPhoto)
class CamperPhotoAdmin(admin.ModelAdmin):

    list_display = ("camper", "caption", "uploaded_at")
    search_fields = ("camper__internal_number", "caption")
