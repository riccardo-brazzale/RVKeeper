from django.urls import path

from . import views


urlpatterns = [
    path("", views.inventory, name="inventory"),
    path("ordini-fornitore/", views.purchase_order_list, name="purchase_order_list"),
    path("ordini-fornitore/nuovo/", views.purchase_order_create, name="purchase_order_create"),
    path("ordini-fornitore/<int:pk>/", views.purchase_order_detail, name="purchase_order_detail"),
    path("ordini-fornitore/<int:pk>/pdf/", views.purchase_order_document, name="purchase_order_pdf"),
    path("ordini-fornitore/<int:pk>/ricezione/", views.purchase_order_receive, name="purchase_order_receive"),
    path("bolle-entrata/<int:pk>/pdf/", views.goods_receipt_document, name="goods_receipt_pdf"),
    path("listini-fornitore/", views.supplier_price_list_list, name="supplier_price_list_list"),
    path("listini-fornitore/importa/", views.supplier_price_list_import, name="supplier_price_list_import"),
    path("listini-fornitore/<int:pk>/", views.supplier_price_list_detail, name="supplier_price_list_detail"),
    path("listini-fornitore/<int:pk>/prezzi/", views.supplier_price_list_grid, name="supplier_price_list_grid"),
    path("listini-fornitore/<int:pk>/aggiungi/", views.supplier_price_list_add_item, name="supplier_price_list_add_item"),
    path("nuovo/", views.part_create, name="part_create"),
    path("<int:pk>/", views.part_detail, name="part_detail"),
    path("<int:pk>/modifica/", views.part_edit, name="part_edit"),
    path("<int:pk>/movimenti/", views.part_movement, name="part_movement"),
    path("<int:part_pk>/fornitori/nuovo/", views.part_supplier_offer, name="part_supplier_offer_create"),
    path("<int:part_pk>/fornitori/<int:offer_pk>/modifica/", views.part_supplier_offer, name="part_supplier_offer_edit"),
    path("<int:part_pk>/allegati/nuovo/", views.part_document_upload, name="part_document_upload"),
]
