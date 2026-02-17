"""
With these settings, tests run faster.
"""

from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="uKL3rIJDB6AmNzHbz48fQlrt3AekIsCMsXT7bQflC3TtfFRVElRrDVL6MuEJCuCY",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES[-1]["OPTIONS"]["loaders"] = [  # type: ignore[index] # noqa F405
    (
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    )
]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CELERY_TASK_ALWAYS_EAGER = True

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"


# Your stuff...
# ------------------------------------------------------------------------------

ENV_NAME = "test"
ENVERGO_AMENAGEMENT_DOMAIN = "testserver"

RATELIMIT_ENABLE = False

# LOGGING
# ------------------------------------------------------------------------------
# Silence the noisiest loggers during tests (DS API calls, GraphQL transport)
# while keeping other log output visible for debugging.
LOGGING.setdefault("loggers", {})  # noqa F405
LOGGING["loggers"]["envergo.petitions.demarches_simplifiees"] = {"level": "WARNING"}
LOGGING["loggers"]["gql"] = {"level": "WARNING"}
