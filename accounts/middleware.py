from django.conf import settings
from django.utils import translation


class PreferredLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            supported_languages = {code for code, _ in settings.LANGUAGES}
            language = user.preferred_language
            if language in supported_languages:
                translation.activate(language)
                request.LANGUAGE_CODE = language
        return self.get_response(request)
