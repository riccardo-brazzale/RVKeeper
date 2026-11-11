from django.urls import path

from . import views


urlpatterns = [
    path("", views.contact_list, name="customers"),
    path("nuovo/", views.contact_create, name="customer_create"),
    path("<int:pk>/modifica/", views.contact_edit, name="customer_edit"),
]
