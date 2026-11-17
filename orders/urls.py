from django.urls import path

from . import views


urlpatterns = [
    path("articoli-manodopera/", views.labor_article_list, name="labor_articles"),
    path("articoli-manodopera/nuovo/", views.labor_article_form, name="labor_article_create"),
    path("articoli-manodopera/<int:pk>/modifica/", views.labor_article_form, name="labor_article_edit"),
    path("", views.work_order_list, name="orders"),
    path("nuovo/", views.work_order_create, name="order_create"),
    path("<int:pk>/", views.work_order_detail, name="work_order_detail"),
    path("<int:pk>/stato/", views.work_order_status, name="order_status"),
    path("<int:pk>/prospetto-pdf/", views.work_order_report, name="work_order_report"),
]
