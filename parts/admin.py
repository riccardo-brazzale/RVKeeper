from django.contrib import admin

from .models import (
    ArticleClass,
    ArticleGroup,
    GoodsReceipt,
    GoodsReceiptLine,
    JobPartUsage,
    Part,
    PartDocument,
    PartMovement,
    PartSupplierOffer,
    PartsRequest,
    PurchaseOrder,
    PurchaseOrderDemand,
    PurchaseOrderLine,
    SupplierPriceList,
    SupplierPriceListItem,
    TransferSlip,
    TransferSlipLine,
    WarehouseNote,
    WarehouseNoteRead,
)


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "supplier", "workshop", "status", "order_date", "created_by")
    list_filter = ("workshop", "status", "order_date")
    search_fields = ("order_number", "supplier__company_name", "supplier__last_name")
    inlines = (PurchaseOrderLineInline,)


@admin.register(PurchaseOrderDemand)
class PurchaseOrderDemandAdmin(admin.ModelAdmin):
    list_display = ("purchase_order_line", "parts_request", "quantity_requested", "quantity_received")
    search_fields = ("parts_request__work_order__ro_number", "purchase_order_line__purchase_order__order_number")


@admin.register(PurchaseOrderLine)
class PurchaseOrderLineAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "part", "quantity_required", "quantity_ordered", "quantity_received", "unit_price")
    list_filter = ("purchase_order__status",)
    search_fields = ("purchase_order__order_number", "part__part_number")


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 0


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "purchase_order", "workshop", "received_at", "received_by")
    list_filter = ("workshop", "received_at")
    search_fields = ("receipt_number", "purchase_order__order_number")
    inlines = (GoodsReceiptLineInline,)


@admin.register(GoodsReceiptLine)
class GoodsReceiptLineAdmin(admin.ModelAdmin):
    list_display = ("goods_receipt", "purchase_order_line", "quantity_received")
    search_fields = ("goods_receipt__receipt_number", "purchase_order_line__part__part_number")


class TransferSlipLineInline(admin.TabularInline):
    model = TransferSlipLine
    extra = 0


@admin.register(TransferSlip)
class TransferSlipAdmin(admin.ModelAdmin):
    list_display = ("work_order", "status", "workshop", "created_by", "created_at", "closed_at")
    list_filter = ("workshop", "status", "created_at")
    search_fields = ("work_order__ro_number",)
    inlines = (TransferSlipLineInline,)


@admin.register(TransferSlipLine)
class TransferSlipLineAdmin(admin.ModelAdmin):
    list_display = ("transfer_slip", "part", "quantity_requested", "quantity_reserved", "status")
    list_filter = ("status",)
    search_fields = ("transfer_slip__work_order__ro_number", "part__part_number")


@admin.register(ArticleClass)
class ArticleClassAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "workshop", "is_active")
    list_filter = ("workshop", "is_active")
    search_fields = ("code", "name")


@admin.register(ArticleGroup)
class ArticleGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "article_class", "workshop", "is_active")
    list_filter = ("workshop", "article_class", "is_active")
    search_fields = ("code", "name")


@admin.register(PartMovement)
class PartMovementAdmin(admin.ModelAdmin):
    list_display = ("part", "movement_type", "quantity", "work_order", "unit_cost", "created_by", "created_at")
    list_filter = ("movement_type", "work_order", "created_at")
    search_fields = ("part__part_number", "work_order__ro_number", "note")


class SupplierPriceListItemInline(admin.TabularInline):
    model = SupplierPriceListItem
    extra = 0


@admin.register(SupplierPriceList)
class SupplierPriceListAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "supplier", "workshop", "is_active", "valid_from")
    list_filter = ("workshop", "supplier", "is_active")
    search_fields = ("code", "name")
    inlines = (SupplierPriceListItemInline,)


@admin.register(SupplierPriceListItem)
class SupplierPriceListItemAdmin(admin.ModelAdmin):
    list_display = ("price_list", "part", "internal_article_code", "supplier_article_code", "unit_price", "discount_percent")
    search_fields = ("price_list__code", "part__part_number", "internal_article_code", "supplier_code")


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
