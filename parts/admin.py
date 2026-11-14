from django.contrib import admin

from .models import Part, PartDocument, PartSupplierOffer


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
