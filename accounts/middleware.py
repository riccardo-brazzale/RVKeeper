from django.conf import settings
from django.contrib.auth import logout
from django.utils import translation
from django.utils import timezone
from datetime import datetime

from .models import AuthenticationSettings


SESSION_LOGIN_AT = "_rvkeeper_login_at"
SESSION_ACTIVITY_AT = "_rvkeeper_activity_at"


class PreferredLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            supported_languages = {code for code, _ in settings.LANGUAGES}
            language = user.preferred_language
            if language and language in supported_languages:
                translation.activate(language)
                request.LANGUAGE_CODE = language
        return self.get_response(request)


class AuthenticationSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            security = AuthenticationSettings.get_solo()
            now = timezone.now()

            login_at = request.session.get(SESSION_LOGIN_AT)
            activity_at = request.session.get(SESSION_ACTIVITY_AT)

            if login_at is None:
                request.session[SESSION_LOGIN_AT] = now.isoformat()
                login_at = now.isoformat()
            if activity_at is None:
                request.session[SESSION_ACTIVITY_AT] = now.isoformat()
                activity_at = now.isoformat()

            login_time = datetime.fromisoformat(login_at)
            last_activity = datetime.fromisoformat(activity_at)
            login_time = timezone.make_aware(login_time) if timezone.is_naive(login_time) else login_time
            last_activity = timezone.make_aware(last_activity) if timezone.is_naive(last_activity) else last_activity

            idle_expired = now - last_activity >= timezone.timedelta(
                minutes=security.idle_timeout_minutes
            )
            absolute_expired = now - login_time >= timezone.timedelta(
                hours=security.session_duration_hours
            )

            if idle_expired or absolute_expired:
                logout(request)
            else:
                request.session[SESSION_ACTIVITY_AT] = now.isoformat()

        return self.get_response(request)
