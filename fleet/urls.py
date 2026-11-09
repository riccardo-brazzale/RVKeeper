from django.urls import path

from . import views

app_name = "fleet"

urlpatterns = [
    path("", views.camper_list, name="camper_list"),
    path("nuovo/", views.camper_create, name="camper_create"),
    path("<str:module>/", views.workflow_list, name="workflow_list"),
    path("<str:module>/nuovo/", views.workflow_create, name="workflow_create"),
    path("<str:module>/<int:pk>/modifica/", views.workflow_edit, name="workflow_edit"),
]
