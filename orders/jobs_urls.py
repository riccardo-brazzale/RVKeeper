from django.urls import path

from . import views


urlpatterns = [
    path("", views.job_list, name="jobs"),
    path("nuovo/", views.job_create, name="job_create"),
    path("<int:pk>/<str:action>/", views.job_action, name="job_action"),
]
