from types import SimpleNamespace
from unittest.mock import Mock

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import translation

from .models import User
from .middleware import PreferredLanguageMiddleware


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

    def test_anonymous_request_does_not_override_active_language(self):
        self.request.user = SimpleNamespace(is_authenticated=False)
        get_response = Mock(side_effect=lambda request: translation.get_language())

        with translation.override("en-us"):
            response_language = PreferredLanguageMiddleware(get_response)(self.request)

        self.assertEqual(response_language, "en-us")
        self.assertFalse(hasattr(self.request, "LANGUAGE_CODE"))


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
        self.assertEqual(self.user.preferred_language, "en-us")
