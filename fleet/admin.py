
from django.contrib import admin
from .models import (CamperOwner, Camper, CamperPhoto, WorkOrder, Job, Part,
                     PartsRequest, WarrantyClaim, WarrantyReturn, JobNote,
                     Attachment, Notification, TimeEvent, JobAssignment, AuditLog)


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


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("ro_number", "customer_name", "status", "workshop", "created_at")
    list_filter = ("workshop", "status", "work_classification", "warranty_status")
    search_fields = ("ro_number", "customer_name", "customer_email", "vehicle__plate")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "work_order", "assigned_to", "status", "workshop")
    list_filter = ("workshop", "department", "specialty", "status")
    search_fields = ("title", "work_order__ro_number", "description")


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("part_number", "name", "quantity", "min_stock", "workshop")
    list_filter = ("workshop",)
    search_fields = ("part_number", "name", "location")


for workflow_model in (PartsRequest, WarrantyClaim, WarrantyReturn, JobNote,
                       Attachment, Notification, TimeEvent, JobAssignment, AuditLog):
    admin.site.register(workflow_model)
