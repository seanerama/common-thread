import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENV = os.environ.get("APP_ENV", "development")
if APP_ENV not in {"development", "test", "production"}:
    raise ImproperlyConfigured("Invalid APP_ENV")
PRODUCTION = APP_ENV == "production"
for required in ("DATABASE_URL", "DJANGO_SECRET_KEY") + (
    ("ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS") if PRODUCTION else ()
):
    if not os.environ.get(required):
        raise ImproperlyConfigured(f"Missing {required}")
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(
    ","
)
CSRF_TRUSTED_ORIGINS = [
    x for x in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if x
]
if PRODUCTION and any(not x.startswith("https://") for x in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("Production origins must use HTTPS")
DATABASES = {
    "default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=0)
}
DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 2
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("PostgreSQL is required")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "crm",
]
MIDDLEWARE = [
    "crm.middleware.RequestLogMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "crm.middleware.PersonApiInputMiddleware",
    "crm.middleware.PeopleManagementGateMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]
ROOT_URLCONF = "common_thread.urls"
WSGI_APPLICATION = "common_thread.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "crm.context_processors.feature_flags",
            ]
        },
    }
]
AUTH_USER_MODEL = "crm.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_AGE = 43200
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = PRODUCTION
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = PRODUCTION
CSRF_FAILURE_VIEW = "crm.views.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if PRODUCTION else 0
SECURE_SSL_REDIRECT = PRODUCTION
SECURE_REDIRECT_EXEMPT = [r"^health/(live|ready)/$"]
# Enable only behind an ingress that strips untrusted forwarded headers.
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if os.environ.get("TRUST_PROXY_HTTPS") == "true"
    else None
)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Bounded HTML forms support percent-encoded Unicode; JSON retains 16 KiB.
DATA_UPLOAD_MAX_MEMORY_SIZE = 262144
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {"json": {"()": "crm.middleware.SafeJsonFormatter"}},
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["stdout"], "level": "INFO"},
}

# Environment changes take effect after restarting the application processes.
PEOPLE_MANAGEMENT_ENABLED = (
    os.environ.get("PEOPLE_MANAGEMENT_ENABLED", "false").lower() == "true"
)

CONTEXT_NOTES_ENABLED = (
    os.environ.get("CONTEXT_NOTES_ENABLED", "false").lower() == "true"
)

PARTY_DIRECTORY_ENABLED = (
    os.environ.get("PARTY_DIRECTORY_ENABLED", "false").lower() == "true"
)

RELATIONSHIPS_ENABLED = (
    os.environ.get("RELATIONSHIPS_ENABLED", "false").lower() == "true"
)

INTERACTIONS_ENABLED = os.environ.get("INTERACTIONS_ENABLED", "false").lower() == "true"
