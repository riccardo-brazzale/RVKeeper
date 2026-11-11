from django.contrib import admin

from .models import CamperOwner, ContactDocument


@admin.register(CamperOwner)
class CamperOwnerAdmin(admin.ModelAdmin):
    list_display = ("__str__", "kind", "workshop", "phone", "email")
    list_filter = ("workshop", "kind", "is_company")
    search_fields = ("company_name", "first_name", "last_name", "email", "vat_number")


@admin.register(ContactDocument)
class ContactDocumentAdmin(admin.ModelAdmin):
    list_display = ("contact", "category", "caption", "created_at")
    list_filter = ("category", "created_at")
    search_fields = ("contact__company_name", "contact__last_name", "caption")
