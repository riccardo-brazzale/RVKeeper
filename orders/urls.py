from django.urls import path

from . import views


urlpatterns = [
    path("listini/", views.price_list_list, name="price_lists"),
    path("listini/nuovo/", views.price_list_form, name="price_list_create"),
    path("listini/<int:pk>/ruota/", views.price_list_rotate, name="price_list_rotate"),
    path("listini/<int:pk>/modifica/", views.price_list_form, name="price_list_edit"),
    path("", views.work_order_list, name="orders"),
    path("nuovo/", views.work_order_create, name="order_create"),
    path("<int:pk>/fatturazione/", views.work_order_billing, name="work_order_billing"),
    path("<int:pk>/", views.work_order_detail, name="work_order_detail"),
    path("<int:pk>/stato/", views.work_order_status, name="order_status"),
    path("<int:pk>/prospetto-pdf/", views.work_order_report, name="work_order_report"),
]
