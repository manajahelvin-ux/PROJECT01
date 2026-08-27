"""
DataExtract AI - Base Django Settings
======================================
Shared settings across all environments.
Environment-specific overrides in dev.py / prod.py.
"""

import os
from pathlib import Path

import environ

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BASE_DIR / "config"

# --- Environment Variables ---
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    DATABASE_URL=(str, "sqlite:///db.sqlite3"),
    REDIS_URL=(str, "redis://localhost:6379/0"),
    CELERY_BROKER_URL=(str, "redis://localhost:6379/0"),
    CELERY_RESULT_BACKEND=(str, "redis://localhost:6379/0"),
    OPENROUTER_API_KEY=(str, ""),
    OPENROUTER_MODEL=(str, "anthropic/claude-3.5-sonnet"),
    OPENROUTER_TEMPERATURE=(float, 0.1),
    OPENROUTER_MAX_TOKENS=(int, 4096),
    OPENROUTER_TIMEOUT=(int, 60),
    PLAYWRIGHT_ENABLED=(bool, True),
    PLAYWRIGHT_TIMEOUT=(int, 30000),
    PLAYWRIGHT_HEADLESS=(bool, True),
    DEFAULT_REQUEST_DELAY_SECONDS=(float, 2.0),
    MAX_CONCURRENT_REQUESTS_PER_DOMAIN=(int, 2),
    MAX_PAGES_PER_EXTRACTION=(int, 100),
    MAX_RESPONSE_SIZE_KB=(int, 5120),
    USER_AGENT_ROTATION=(bool, True),
    DATA_RETENTION_DAYS=(int, 365),
    SENTRY_DSN=(str, ""),
)

# Read .env file if it exists
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# --- Core Django Settings ---
SECRET_KEY = env("SECRET_KEY", default="change-me-to-a-long-random-string")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# --- Application Definition ---
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.authentication",
    "apps.dashboard",
    "apps.projects",
    "apps.scraping",
    "apps.extraction",
    "apps.datasets",
    "apps.ai_engine",
    "apps.quality",
    "apps.exports",
    "apps.integrations",
    "apps.scheduling",
    "apps.knowledge_base",
    "apps.logs",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --- Middleware ---
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# --- URL & WSGI ---
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Templates ---
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database ---
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# --- Password Validation ---
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalization ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static Files ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# --- Media Files ---
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Default Primary Key ---
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Custom User Model ---
AUTH_USER_MODEL = "authentication.User"

# --- Authentication ---
LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/auth/login/"

# --- Django REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "EXCEPTION_HANDLER": "config.exceptions.custom_exception_handler",
}

# --- DRF Spectacular (OpenAPI / Swagger) ---
SPECTACULAR_SETTINGS = {
    "TITLE": "DataExtract AI API",
    "DESCRIPTION": "Web Data Extraction, Structuration, Quality & AI Platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
}

# --- Celery Configuration ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 minutes soft limit
CELERY_BEAT_SCHEDULE = {}

# --- Redis Cache ---
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    }
}

# --- OpenRouter AI Settings ---
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY")
OPENROUTER_MODEL = env("OPENROUTER_MODEL")
OPENROUTER_TEMPERATURE = env("OPENROUTER_TEMPERATURE")
OPENROUTER_MAX_TOKENS = env("OPENROUTER_MAX_TOKENS")
OPENROUTER_TIMEOUT = env("OPENROUTER_TIMEOUT")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- Scraping Defaults ---
DEFAULT_REQUEST_DELAY_SECONDS = env("DEFAULT_REQUEST_DELAY_SECONDS")
MAX_CONCURRENT_REQUESTS_PER_DOMAIN = env("MAX_CONCURRENT_REQUESTS_PER_DOMAIN")
MAX_PAGES_PER_EXTRACTION = env("MAX_PAGES_PER_EXTRACTION")
MAX_RESPONSE_SIZE_KB = env("MAX_RESPONSE_SIZE_KB")
USER_AGENT_ROTATION = env("USER_AGENT_ROTATION")

# --- Playwright Settings ---
PLAYWRIGHT_ENABLED = env("PLAYWRIGHT_ENABLED")
PLAYWRIGHT_TIMEOUT = env("PLAYWRIGHT_TIMEOUT")
PLAYWRIGHT_HEADLESS = env("PLAYWRIGHT_HEADLESS")

# --- Data Retention ---
DATA_RETENTION_DAYS = env("DATA_RETENTION_DAYS")

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
