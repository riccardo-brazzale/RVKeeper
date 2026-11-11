from django.urls import path

from . import views


urlpatterns = [
    path("", views.quote_list, name="quotes"),
    path("nuovo/", views.quote_create, name="quote_create"),
    path("<int:pk>/", views.quote_detail, name="quote_detail"),
    path("<int:pk>/modifica/", views.quote_edit, name="quote_edit"),
    path("<int:pk>/stato/", views.quote_status, name="quote_status"),
    path("<int:pk>/crea-odl/", views.quote_to_order, name="quote_to_order"),
]
