import os
from .settings import *

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False


def _env_bool(name, default):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name):
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS") or ["localhost", "127.0.0.1"]
_server_name = os.getenv("RVKEEPER_SERVER_NAME", "").strip()
_tls_configured = bool(
    os.getenv("RVKEEPER_TLS_CERTIFICATE", "").strip()
    and os.getenv("RVKEEPER_TLS_KEY", "").strip()
)
_secure_default = "true" if _tls_configured else "false"
_csrf_default = f"https://{_server_name}" if _tls_configured and _server_name else (
    f"http://{_server_name}" if _server_name else ""
)
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS") or (
    [_csrf_default] if _csrf_default else []
)
STATIC_URL = "/static/"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SECURE_COOKIES", _secure_default)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_SECURE_COOKIES", _secure_default)
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", _secure_default)

# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", os.getenv("SMTP_HOST", ""))
EMAIL_PORT = int(os.getenv("EMAIL_PORT", os.getenv("SMTP_PORT", "587")))
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", "true")
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", "false")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", os.getenv("SMTP_USER", ""))
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "webmaster@localhost")
