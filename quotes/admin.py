from django.contrib import admin

from .models import Quote, QuoteLine


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 0


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("quote_number", "customer", "vehicle", "status", "valid_until", "workshop", "created_at")
    list_filter = ("workshop", "status", "valid_until")
    search_fields = ("quote_number", "customer__company_name", "vehicle__plate")
    inlines = (QuoteLineInline,)


@admin.register(QuoteLine)
class QuoteLineAdmin(admin.ModelAdmin):
    list_display = ("quote", "line_type", "description", "quantity", "unit", "unit_price", "discount_percent")
    list_filter = ("line_type",)
    search_fields = ("quote__quote_number", "description", "part__part_number")
