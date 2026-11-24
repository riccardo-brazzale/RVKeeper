from django.contrib import admin

from .models import (
    JobPartUsage,
    Part,
    PartDocument,
    PartSupplierOffer,
    PartsRequest,
    WarehouseNote,
    WarehouseNoteRead,
)


@admin.register(PartsRequest)
class PartsRequestAdmin(admin.ModelAdmin):
    list_display = ("work_order", "part", "status", "quantity_requested", "requested_by", "created_at")
    list_filter = ("workshop", "status", "created_at")
    search_fields = ("work_order__ro_number", "part__part_number", "custom_item")


@admin.register(JobPartUsage)
class JobPartUsageAdmin(admin.ModelAdmin):
    list_display = ("job", "part", "quantity_used", "used_by", "created_at")
    list_filter = ("workshop", "created_at")
    search_fields = ("job__title", "part__part_number", "used_by__username")


@admin.register(WarehouseNote)
class WarehouseNoteAdmin(admin.ModelAdmin):
    list_display = ("work_order", "part", "author", "estimated_delivery_at", "created_at")
    list_filter = ("workshop", "created_at")
    search_fields = ("work_order__ro_number", "part__part_number", "text")


@admin.register(WarehouseNoteRead)
class WarehouseNoteReadAdmin(admin.ModelAdmin):
    list_display = ("note", "recipient", "read_at")
    list_filter = ("read_at",)
    search_fields = ("note__work_order__ro_number", "recipient__username")


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("part_number", "name", "workshop", "quantity", "min_stock", "location")
    list_filter = ("workshop",)
    search_fields = ("part_number", "name", "description", "location")


@admin.register(PartSupplierOffer)
class PartSupplierOfferAdmin(admin.ModelAdmin):
    list_display = ("part", "supplier", "purchase_price", "discount_percent", "is_preferred", "updated_at")
    list_filter = ("is_preferred", "part__workshop")
    search_fields = ("part__part_number", "part__name", "supplier__company_name", "supplier__last_name")


@admin.register(PartDocument)
class PartDocumentAdmin(admin.ModelAdmin):
    list_display = ("part", "category", "caption", "created_at")
    list_filter = ("category", "created_at")
    search_fields = ("part__part_number", "part__name", "caption")
