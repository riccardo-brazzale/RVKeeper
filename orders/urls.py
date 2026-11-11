from django.urls import path

from . import views


urlpatterns = [
    path("", views.work_order_list, name="orders"),
    path("nuovo/", views.work_order_create, name="order_create"),
    path("<int:pk>/stato/", views.work_order_status, name="order_status"),
    path("<int:pk>/prospetto-pdf/", views.work_order_report, name="work_order_report"),
]
