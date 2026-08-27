"""
DataExtract AI - Production Settings
======================================
Overrides for production environment.
"""

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

from .base import *  # noqa: F401, F403

# --- Production Security ---
DEBUG = False

# --- Sentry ---
SENTRY_DSN = env("SENTRY_DSN")  # noqa: F405
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )

# --- Security Settings ---
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"

# --- Static files with WhiteNoise ---
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- Database: enforce PostgreSQL in production ---
import dj_database_url  # noqa: E402

DATABASES["default"] = dj_database_url.config(  # noqa: F405
    conn_max_age=600,
    conn_health_checks=True,
)

# --- CORS: restrict in production ---
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])  # noqa: F405

# --- Rate Limiting ---
RATELIMIT_ENABLE = True

# --- Logging: production level ---
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["handlers"]["file"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": str(BASE_DIR / "logs" / "dataextract.log"),  # noqa: F405
    "maxBytes": 10 * 1024 * 1024,  # 10 MB
    "backupCount": 5,
    "formatter": "verbose",
}
LOGGING["root"]["handlers"] = ["console", "file"]  # noqa: F405
