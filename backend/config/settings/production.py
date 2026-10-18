import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured in production.")

DEBUG = False
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be configured in production.")
if os.getenv("DB_ENGINE", "").lower() != "postgresql":
    raise ImproperlyConfigured("Production requires DB_ENGINE=postgresql.")
if not os.getenv("DATABASE_URL"):
    _missing_db_vars = [
        name for name in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST") if not os.getenv(name)
    ]
else:
    _missing_db_vars = []
if _missing_db_vars:
    raise ImproperlyConfigured(
        "Set DATABASE_URL or provide required database environment variables: "
        + ", ".join(_missing_db_vars)
    )

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"