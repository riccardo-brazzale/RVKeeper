from django.contrib import admin

from .models import Camper, CamperPhoto


@admin.register(Camper)
class CamperAdmin(admin.ModelAdmin):
    list_display = ("internal_number", "plate", "brand", "model", "owner", "workshop", "is_active")
    list_filter = ("workshop", "is_active", "fuel_type", "transmission")
    search_fields = ("internal_number", "plate", "vin", "brand", "model", "owner__company_name", "owner__last_name")


@admin.register(CamperPhoto)
class CamperPhotoAdmin(admin.ModelAdmin):
    list_display = ("camper", "category", "caption", "uploaded_at")
    list_filter = ("category", "uploaded_at")
    search_fields = ("camper__plate", "camper__internal_number", "caption")
