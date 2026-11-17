from django.urls import path

from . import views


urlpatterns = [
    path("miei/", views.my_jobs, name="my_jobs"),
    path("", views.job_list, name="jobs"),
    path("nuovo/", views.job_create, name="job_create"),
    path("<int:pk>/parts-request/", views.job_parts_request, name="job_parts_request"),
    path("<int:pk>/complete/", views.job_complete, name="job_complete"),
    path("<int:pk>/<str:action>/", views.job_action, name="job_action"),
]
