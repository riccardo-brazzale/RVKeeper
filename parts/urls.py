from django.urls import path

from . import views


urlpatterns = [
    path("", views.inventory, name="inventory"),
    path("nuovo/", views.part_create, name="part_create"),
    path("<int:pk>/", views.part_detail, name="part_detail"),
    path("<int:pk>/modifica/", views.part_edit, name="part_edit"),
    path("<int:pk>/movimenti/", views.part_movement, name="part_movement"),
    path("<int:part_pk>/fornitori/nuovo/", views.part_supplier_offer, name="part_supplier_offer_create"),
    path("<int:part_pk>/fornitori/<int:offer_pk>/modifica/", views.part_supplier_offer, name="part_supplier_offer_edit"),
    path("<int:part_pk>/allegati/nuovo/", views.part_document_upload, name="part_document_upload"),
]
