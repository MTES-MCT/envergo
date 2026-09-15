"""Settings for local load testing.

Production-like performance flags, every outbound channel pinned to a
local backend and asserted at import: a stray env var (e.g. via .env)
kills boot instead of arming a real channel.
"""

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

# Tasks run inline; their side effects stay under the assertions below.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# A single-IP load generator would hit the per-IP rate limit immediately
# and measure the limiter, not the app.
MIDDLEWARE = [
    m
    for m in MIDDLEWARE
    if m != "envergo.middleware.rate_limiting.RateLimitingMiddleware"
]

# Fail at boot if any outbound channel is armed.
assert not DEMARCHE_NUMERIQUE["ENABLED"], "DS API must stay disabled"
assert MATTERMOST_ENDPOINT_HAIE is None, "Mattermost (haie) must stay unset"
assert MATTERMOST_ENDPOINT_AMENAGEMENT is None, "Mattermost must stay unset"
assert MAKE_COM_WEBHOOK is None, "make.com webhook must stay unset"
assert MAKE_COM_EVALUATION_EDITION_WEBHOOK is None, "make.com webhook must stay unset"
assert BREVO["API_KEY"] is None, "Brevo API key must stay unset"
