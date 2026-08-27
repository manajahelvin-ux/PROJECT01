"""
DataExtract AI - Development Settings
======================================
Overrides for local development environment.
"""

from .base import *  # noqa: F401, F403

# --- Development Overrides ---
DEBUG = True

ALLOWED_HOSTS = ["*"]

# --- Debug Toolbar ---
INSTALLED_APPS += ["debug_toolbar", "django_extensions"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1", "localhost"]

# --- Email (console for dev) ---
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- CORS (allow all in dev) ---
CORS_ALLOW_ALL_ORIGINS = True

# --- Simplified cache for dev (fallback to local memory if Redis unavailable) ---
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dataextract-dev",
    }
}

# --- Celery: eager mode for dev (run tasks synchronously) ---
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# --- Logging: more verbose in dev ---
LOGGING["root"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["django"]["level"] = "DEBUG"  # noqa: F405
