"""Settings for local load testing.

Performance flags match production. Every outbound channel stays local.
Boot fails if an environment variable arms a real channel.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa
from .base import (
    BREVO,
    DEMARCHE_NUMERIQUE,
    MAKE_COM_EVALUATION_EDITION_WEBHOOK,
    MAKE_COM_WEBHOOK,
    MATTERMOST_ENDPOINT_AMENAGEMENT,
    MATTERMOST_ENDPOINT_HAIE,
    MIDDLEWARE,
    TEMPLATES,
    env,
)

DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY", default="loadtest-only-not-a-secret")

ENV_NAME = "loadtest"
ENVERGO_AMENAGEMENT_DOMAIN = "envergo.local"
ENVERGO_HAIE_DOMAIN = "haie.local"

ALLOWED_HOSTS = ["haie.local", "envergo.local", "localhost", "127.0.0.1"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "loadtest",
    }
}

# Prod parity: cached template loader
TEMPLATES[0]["OPTIONS"]["loaders"] = [
    (
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    ),
]

# Static assets are outside the load scenarios: no compress build needed.
COMPRESS_ENABLED = False

# Outbound channels: pinned local, never networked.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "upload": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

# Tasks run inline, so the guards below also cover their side effects.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# A single-IP load generator would hit the per-IP rate limit immediately
# and measure the limiter, not the app.
rate_limiting_middleware = "envergo.middleware.rate_limiting.RateLimitingMiddleware"
if rate_limiting_middleware not in MIDDLEWARE:
    raise ImproperlyConfigured(
        f"Rate limiter not found at {rate_limiting_middleware}. If it moved, "
        "update the path here, or the load test measures the limiter."
    )
MIDDLEWARE = [
    middleware for middleware in MIDDLEWARE if middleware != rate_limiting_middleware
]

# Fail at boot if any outbound channel is armed.
is_armed_by_channel = {
    "DS API": DEMARCHE_NUMERIQUE["ENABLED"],
    "Mattermost (haie)": MATTERMOST_ENDPOINT_HAIE is not None,
    "Mattermost (aménagement)": MATTERMOST_ENDPOINT_AMENAGEMENT is not None,
    "make.com webhook": MAKE_COM_WEBHOOK is not None,
    "make.com evaluation webhook": MAKE_COM_EVALUATION_EDITION_WEBHOOK is not None,
    "Brevo API key": BREVO["API_KEY"] is not None,
}
armed_channels = [name for name, is_armed in is_armed_by_channel.items() if is_armed]
if armed_channels:
    raise ImproperlyConfigured(
        f"Outbound channels must stay disabled: {', '.join(armed_channels)}"
    )
