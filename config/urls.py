
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from . import views


urlpatterns = [
    path("", views.home, name="home"),

    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True
        ),
        name="login"
    ),

    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout"
    ),

    path("admin/", admin.site.urls),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
