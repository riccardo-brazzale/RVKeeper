from django.urls import path

from . import views

app_name = "fleet"

urlpatterns = [
    path("veicolo/<int:pk>/", views.camper_detail, name="camper_detail"),
    path("veicolo/<int:pk>/modifica/", views.camper_edit, name="camper_edit"),
    path("veicolo/<int:pk>/foto/", views.camper_photo_upload, name="camper_photo_upload"),
    path("ricambio/<int:pk>/movimenti/", views.part_movement, name="part_movement"),
    path("", views.camper_list, name="camper_list"),
    path("nuovo/", views.camper_create, name="camper_create"),
    path("<str:module>/", views.workflow_list, name="workflow_list"),
    path("<str:module>/nuovo/", views.workflow_create, name="workflow_create"),
    path("<str:module>/<int:pk>/modifica/", views.workflow_edit, name="workflow_edit"),
]
