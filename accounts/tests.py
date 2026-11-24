from types import SimpleNamespace
from unittest.mock import Mock

from django.core import mail
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.contrib.auth import login
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.backends.db import SessionStore
from django.utils import translation
from django.utils import timezone
from django.urls import reverse

from .models import AuthenticationSettings, User
from .middleware import (
    AuthenticationSessionMiddleware,
    PreferredLanguageMiddleware,
    SESSION_ACTIVITY_AT,
    SESSION_LOGIN_AT,
)


class PreferredLanguageMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")

    def test_authenticated_user_preference_activates_supported_language(self):
        self.request.user = SimpleNamespace(
            is_authenticated=True,
            preferred_language="it",
        )
        get_response = Mock(side_effect=lambda request: translation.get_language())

        with translation.override("en-us"):
            response_language = PreferredLanguageMiddleware(get_response)(self.request)

        self.assertEqual(response_language, "it")
        self.assertEqual(self.request.LANGUAGE_CODE, "it")
        get_response.assert_called_once_with(self.request)

    def test_unsupported_preference_leaves_locale_middleware_language_unchanged(self):
        self.request.user = SimpleNamespace(
            is_authenticated=True,
            preferred_language="fr",
        )
        get_response = Mock(side_effect=lambda request: translation.get_language())

        with translation.override("en-us"):
            response_language = PreferredLanguageMiddleware(get_response)(self.request)

        self.assertEqual(response_language, "en-us")
        self.assertFalse(hasattr(self.request, "LANGUAGE_CODE"))

    def test_browser_preference_leaves_locale_middleware_language_unchanged(self):
        self.request.user = SimpleNamespace(
            is_authenticated=True,
            preferred_language="",
        )
        self.request.LANGUAGE_CODE = "it"
        get_response = Mock(side_effect=lambda request: translation.get_language())

        with translation.override("it"):
            response_language = PreferredLanguageMiddleware(get_response)(self.request)

        self.assertEqual(response_language, "it")
        self.assertEqual(self.request.LANGUAGE_CODE, "it")

    def test_anonymous_request_does_not_override_active_language(self):
        self.request.user = SimpleNamespace(is_authenticated=False)
        get_response = Mock(side_effect=lambda request: translation.get_language())

        with translation.override("en-us"):
            response_language = PreferredLanguageMiddleware(get_response)(self.request)

        self.assertEqual(response_language, "en-us")
        self.assertFalse(hasattr(self.request, "LANGUAGE_CODE"))


class AuthenticationSessionMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="session-test",
            email="session-test@example.com",
            password="test-password",
        )
        self.security = AuthenticationSettings.get_solo()

    def make_request(self):
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        login(request, self.user)
        request.session[SESSION_LOGIN_AT] = timezone.now().isoformat()
        request.session[SESSION_ACTIVITY_AT] = timezone.now().isoformat()
        return request

    def test_idle_timeout_logs_out_authenticated_user(self):
        request = self.make_request()
        request.session[SESSION_ACTIVITY_AT] = (
            timezone.now() - timezone.timedelta(minutes=16)
        ).isoformat()

        AuthenticationSessionMiddleware(lambda req: req)(request)

        self.assertNotIn("_auth_user_id", request.session)

    def test_absolute_session_duration_logs_out_authenticated_user(self):
        request = self.make_request()
        request.session[SESSION_LOGIN_AT] = (
            timezone.now() - timezone.timedelta(hours=11)
        ).isoformat()

        AuthenticationSessionMiddleware(lambda req: req)(request)

        self.assertNotIn("_auth_user_id", request.session)

    @override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True)
    def test_browser_close_setting_is_enabled(self):
        self.assertTrue(
            __import__("django.conf").conf.settings.SESSION_EXPIRE_AT_BROWSER_CLOSE
        )


class AdminLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="warehouse",
            email="warehouse@example.com",
            password="test-password",
            profile="warehouse",
        )

    def test_admin_login_always_ends_existing_session(self):
        self.client.force_login(self.user)
        self.assertIn("_auth_user_id", self.client.session)

        response = self.client.get("/admin/login/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_user_change_page_renders(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.get(
            f"/admin/accounts/user/{self.user.pk}/change/",
        )

        self.assertEqual(response.status_code, 200)


class LanguagePreferenceViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="language-test",
            email="language-test@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_user_can_save_italian_as_interface_language(self):
        response = self.client.post(
            "/accounts/preferences/",
            {"preferred_language": "it"},
        )

        self.assertRedirects(response, "/accounts/preferences/")
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, "it")

    def test_user_cannot_save_an_unsupported_interface_language(self):
        response = self.client.post(
            "/accounts/preferences/",
            {"preferred_language": "fr"},
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, "")

    def test_user_can_select_browser_language(self):
        response = self.client.post(
            "/accounts/preferences/",
            {"preferred_language": ""},
        )

        self.assertRedirects(response, "/accounts/preferences/")
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, "")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetRequestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reset-user",
            email="reset-user@example.com",
            password="test-password",
        )

    def test_request_form_requires_username_and_email(self):
        response = self.client.get(reverse("password_reset"))

        self.assertEqual(list(response.context["form"].fields), ["username", "email"])
        self.assertContains(response, "Enter your username and the email address registered to that account.")

    def test_reset_email_is_sent_only_when_username_and_email_belong_together(self):
        for credentials in (
            {"username": "other-user", "email": self.user.email},
            {"username": self.user.username, "email": "other@example.com"},
        ):
            response = self.client.post(reverse("password_reset"), credentials)
            self.assertRedirects(response, reverse("password_reset_done"))
            self.assertEqual(len(mail.outbox), 0)

        response = self.client.post(
            reverse("password_reset"),
            {"username": self.user.username, "email": self.user.email},
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
