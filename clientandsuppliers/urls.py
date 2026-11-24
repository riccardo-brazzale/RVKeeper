from django.urls import path

from . import views


urlpatterns = [
    path("", views.contact_list, name="customers"),
    path("clienti/", views.customer_list, name="customer_list"),
    path("fornitori/", views.supplier_list, name="supplier_list"),
    path("nuovo/", views.contact_create, name="customer_create"),
    path("<int:pk>/", views.contact_detail, name="customer_detail"),
    path("<int:pk>/modifica/", views.contact_edit, name="customer_edit"),
]
