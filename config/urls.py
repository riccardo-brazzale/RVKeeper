
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import reverse_lazy

from fleet import views as fleet_views
from config import admin_ordering  # noqa: F401

admin.site.site_header = "Amministrazione RVKeeper"
admin.site.site_title = "Amministrazione RVKeeper"
admin.site.index_title = "Amministrazione RVKeeper"


urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("", fleet_views.dashboard, name="home"),

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
    path(
        "accounts/password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    path("parco-mezzi/", include("fleet.urls")),
    path("ordini/", fleet_views.workflow_list, {"module": "orders"}, name="orders"),
    path("ordini/nuovo/", fleet_views.workflow_create, {"module": "orders"}, name="order_create"),
    path("ordini/<int:pk>/stato/", fleet_views.workflow_status_action, {"module": "orders"}, name="order_status"),
    path("lavori/", fleet_views.workflow_list, {"module": "jobs"}, name="jobs"),
    path("lavori/nuovo/", fleet_views.workflow_create, {"module": "jobs"}, name="job_create"),
    path("lavori/<int:pk>/<str:action>/", fleet_views.job_action, name="job_action"),
    path("magazzino/", fleet_views.workflow_list, {"module": "parts"}, name="inventory"),
    path("magazzino/nuovo/", fleet_views.workflow_create, {"module": "parts"}, name="part_create"),
    path("richieste-ricambi/", fleet_views.workflow_list, {"module": "requests"}, name="parts_requests"),
    path("richieste-ricambi/nuova/", fleet_views.workflow_create, {"module": "requests"}, name="parts_request_create"),
    path("richieste-ricambi/<int:pk>/stato/", fleet_views.workflow_status_action, {"module": "requests"}, name="parts_request_status"),
    path("richieste-ricambi/<int:pk>/<str:action>/", fleet_views.parts_request_action, name="parts_request_action"),
    path("garanzie/", fleet_views.workflow_list, {"module": "claims"}, name="warranties"),
    path("garanzie/nuova/", fleet_views.workflow_create, {"module": "claims"}, name="warranty_create"),
    path("garanzie/<int:pk>/stato/", fleet_views.workflow_status_action, {"module": "claims"}, name="warranty_status"),
    path("resi/", fleet_views.workflow_list, {"module": "returns"}, name="returns"),
    path("resi/nuovo/", fleet_views.workflow_create, {"module": "returns"}, name="return_create"),
    path("resi/<int:pk>/stato/", fleet_views.workflow_status_action, {"module": "returns"}, name="return_status"),
    path("note/", fleet_views.workflow_list, {"module": "notes"}, name="notes"),
    path("note/nuova/", fleet_views.workflow_create, {"module": "notes"}, name="note_create"),
    path("assegnazioni/", fleet_views.workflow_list, {"module": "assignments"}, name="assignments"),
    path("assegnazioni/nuova/", fleet_views.workflow_create, {"module": "assignments"}, name="assignment_create"),
    path("allegati/", fleet_views.workflow_list, {"module": "attachments"}, name="attachments"),
    path("allegati/nuovo/", fleet_views.workflow_create, {"module": "attachments"}, name="attachment_create"),
    path("report/", fleet_views.report, name="report"),
    path("notifiche/", fleet_views.notifications, name="notifications"),
    path("notifiche/lette/", fleet_views.mark_notifications_read, name="notifications_read"),
    path("registro-attivita/", fleet_views.audit_log, name="audit_log"),
    path("esporta-dati/", fleet_views.data_export, name="data_export"),
    path("flussi/<str:module>/<int:pk>/stato/", fleet_views.workflow_status_action, name="workflow_status_action"),

    path("admin/", admin.site.urls),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
