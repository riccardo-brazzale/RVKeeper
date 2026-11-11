from django.contrib import admin

from .models import PartDocument


@admin.register(PartDocument)
class PartDocumentAdmin(admin.ModelAdmin):
    list_display = ("part", "category", "caption", "created_at")
    list_filter = ("category", "created_at")
    search_fields = ("part__part_number", "part__name", "caption")
