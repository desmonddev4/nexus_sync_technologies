import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-insecure-key")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.patients.apps.PatientsConfig",
    "apps.devices.apps.DevicesConfig",
    "apps.monitoring.apps.MonitoringConfig",
    "apps.incidents.apps.IncidentsConfig",
    "apps.emergency_services.apps.EmergencyServicesConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.audit.apps.AuditConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

database_url = os.getenv("DATABASE_URL", "")
if database_url:
    parsed_database_url = urlparse(database_url)
    if parsed_database_url.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use the postgres:// or postgresql:// scheme.")
    database_options = {}
    if "sslmode" in parse_qs(parsed_database_url.query):
        database_options["sslmode"] = parse_qs(parsed_database_url.query)["sslmode"][-1]
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed_database_url.path.lstrip("/")),
            "USER": unquote(parsed_database_url.username or ""),
            "PASSWORD": unquote(parsed_database_url.password or ""),
            "HOST": parsed_database_url.hostname or "",
            "PORT": str(parsed_database_url.port or "5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": database_options,
        }
    }
elif os.getenv("DB_ENGINE", "sqlite").lower() == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "nexus_sync"),
            "USER": os.getenv("DB_USER", "nexus_sync"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_URLS_REGEX = r"^/api/.*$"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.devices.authentication.DeviceTokenAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SASUSYNC_API_KEY = os.getenv("SASUSYNC_API_KEY", "")
SASUSYNC_SENDER_ID = os.getenv("SASUSYNC_SENDER_ID", "")
SASUSYNC_BASE_URL = os.getenv("SASUSYNC_BASE_URL", "https://sms.sasusync.com")
SASUSYNC_WEBHOOK_SECRET = os.getenv("SASUSYNC_WEBHOOK_SECRET", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Audit retention and export controls
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))
AUDIT_EXPORT_MAX_ROWS = int(os.getenv("AUDIT_EXPORT_MAX_ROWS", "2000"))
PATIENT_DATA_REQUEST_RETENTION_DAYS = int(os.getenv("PATIENT_DATA_REQUEST_RETENTION_DAYS", "365"))
# Face verification is research-only and fail-closed until a vetted implementation is configured.
BIOMETRIC_RESEARCH_ENABLED = os.getenv('BIOMETRIC_RESEARCH_ENABLED', 'false').lower() == 'true'
BIOMETRIC_VERIFIER_CLASS = os.getenv('BIOMETRIC_VERIFIER_CLASS', '')
BIOMETRIC_RESEARCH_CONSENT_VERSION = os.getenv('BIOMETRIC_RESEARCH_CONSENT_VERSION', '')
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {'biometric_capture': '5/day'}
BIOMETRIC_FACE_LOGIN_ENABLED = os.getenv('BIOMETRIC_FACE_LOGIN_ENABLED', 'false').lower() == 'true'
BIOMETRIC_FACE_CONSENT_VERSION = os.getenv('BIOMETRIC_FACE_CONSENT_VERSION', '')
BIOMETRIC_MODEL_NAME = os.getenv('BIOMETRIC_MODEL_NAME', 'buffalo_l')
BIOMETRIC_MODEL_ROOT = os.getenv('BIOMETRIC_MODEL_ROOT', str(BASE_DIR / '.face-model-cache'))
BIOMETRIC_MATCH_THRESHOLD = float(os.getenv('BIOMETRIC_MATCH_THRESHOLD', '0.45'))
BIOMETRIC_FACE_LIVENESS_ENABLED = os.getenv('BIOMETRIC_FACE_LIVENESS_ENABLED', 'false').lower() == 'true'
BIOMETRIC_LIVENESS_THRESHOLD = float(os.getenv('BIOMETRIC_LIVENESS_THRESHOLD', '0.8'))
BIOMETRIC_MOTION_TEST_ENABLED = os.getenv('BIOMETRIC_MOTION_TEST_ENABLED', 'false').lower() == 'true'
BIOMETRIC_MOTION_CONSENT_VERSION = os.getenv('BIOMETRIC_MOTION_CONSENT_VERSION', '')
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].update({
    'biometric_face_login': '5/minute',
    'biometric_liveness_challenge': '10/minute',
    'biometric_motion_test': '5/day',
})
