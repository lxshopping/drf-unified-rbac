import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "development-only-rbac-example-key"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_unified_rbac",
    "demo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
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
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

RBAC_AUTH_MODE = os.environ.get("DRF_RBAC_AUTH_MODE", "local")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        ["drf_unified_rbac.authentication.KeycloakAuthentication"]
        if RBAC_AUTH_MODE == "sso"
        else [
            "rest_framework.authentication.SessionAuthentication",
            "rest_framework.authentication.BasicAuthentication",
        ]
    )
}

DRF_RBAC = {
    "AUTH_MODE": RBAC_AUTH_MODE,
    "KEYCLOAK_ISSUER": os.environ.get("KEYCLOAK_ISSUER"),
    "KEYCLOAK_CLIENT_ID": os.environ.get("KEYCLOAK_CLIENT_ID"),
    # Optional: defaults to KEYCLOAK_CLIENT_ID when omitted.
    "KEYCLOAK_AUDIENCE": os.environ.get("KEYCLOAK_AUDIENCE"),
}
