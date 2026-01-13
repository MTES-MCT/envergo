import logging

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from envergo.utils.csp import CSP

from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env("DJANGO_SECRET_KEY")
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["envergo.beta.gouv.fr"])

# DATABASES
# ------------------------------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)  # noqa F405

# CACHES
# ------------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": env("DJANGO_CACHE_BACKEND"),
        "LOCATION": env("DJANGO_CACHE_LOCATION"),
        "OPTIONS": {
            # Mimicing memcache behavior.
            # https://github.com/jazzband/django-redis#memcached-exceptions-behavior
            "IGNORE_EXCEPTIONS": True,
        },
    }
}

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-ssl-redirect
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-secure
SESSION_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-secure
CSRF_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/topics/security/#ssl-https
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-seconds
# TODO: set this to 60 seconds first and then to 518400 once you prove the former works
SECURE_HSTS_SECONDS = 60
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-include-subdomains
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-preload
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
# https://docs.djangoproject.com/en/dev/ref/middleware/#x-content-type-options-nosniff
SECURE_CONTENT_TYPE_NOSNIFF = env.bool(
    "DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True
)

# STORAGES
# ------------------------------------------------------------------------------
# https://django-storages.readthedocs.io/en/latest/#installation
INSTALLED_APPS += ["storages"]  # noqa F405
AWS_S3_ENDPOINT_URL = env("DJANGO_AWS_S3_ENDPOINT_URL")
AWS_ACCESS_KEY_ID = env("DJANGO_AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("DJANGO_AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("DJANGO_AWS_STORAGE_BUCKET_NAME")
AWS_UPLOAD_BUCKET_NAME = env("DJANGO_AWS_UPLOAD_BUCKET_NAME")
AWS_S3_REGION_NAME = env("DJANGO_AWS_S3_REGION_NAME")
AWS_DEFAULT_ACL = "public-read"
AWS_QUERYSTRING_AUTH = False
AWS_S3_FILE_OVERWRITE = False

# DO NOT change these unless you know what you're doing.
_AWS_EXPIRY = 60 * 60 * 24 * 7
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": f"max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate"
}
AWS_S3_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_CUSTOM_DOMAIN", default=None)
aws_s3_domain = AWS_S3_ENDPOINT_URL

MEDIA_URL = f"https://{aws_s3_domain}/media/"

STORAGES = {
    "default": {"BACKEND": "envergo.utils.storages.MediaRootS3Boto3Storage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
    "upload": {"BACKEND": "envergo.utils.storages.UploadS3Boto3Storage"},
}


# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES[-1]["OPTIONS"]["loaders"] = [  # type: ignore[index] # noqa F405
    (
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    )
]

# https://docs.djangoproject.com/en/dev/ref/settings/#server-email
# https://docs.djangoproject.com/en/dev/ref/settings/#email-subject-prefix
EMAIL_SUBJECT_PREFIX = env(
    "DJANGO_EMAIL_SUBJECT_PREFIX",
    default="[Envergo]",
)

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL regex.
ADMIN_URL = env("DJANGO_ADMIN_URL")

# Anymail
# ------------------------------------------------------------------------------
# https://anymail.readthedocs.io/en/stable/installation/#installing-anymail
INSTALLED_APPS += ["anymail"]  # noqa F405
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
# https://anymail.readthedocs.io/en/stable/installation/#anymail-settings-reference
# https://anymail.readthedocs.io/en/stable/esps/sendinblue/

ENV_NAME = env("ENV_NAME")
IS_REVIEW_APP = env.bool("IS_REVIEW_APP", default=False)

# Different settings between scalingo prod and review apps
if ENV_NAME == "production":
    EMAIL_BACKEND = "anymail.backends.sendinblue.EmailBackend"
else:
    # Send emails to stdout for logging purpose
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

ANYMAIL = {
    "SENDINBLUE_API_KEY": env("SENDINBLUE_API_KEY"),
    "SENDINBLUE_API_URL": env(
        "SENDINBLUE_API_URL", default="https://api.sendinblue.com/v3/"
    ),
    "WEBHOOK_SECRET": env("SENDINBLUE_WEBHOOK_SECRET"),
}

# django-compressor
# ------------------------------------------------------------------------------
# https://django-compressor.readthedocs.io/en/latest/settings/#django.conf.settings.COMPRESS_ENABLED
COMPRESS_ENABLED = env.bool("COMPRESS_ENABLED", default=True)
# https://django-compressor.readthedocs.io/en/latest/settings/#django.conf.settings.COMPRESS_URL
COMPRESS_URL = STATIC_URL  # noqa F405
# https://django-compressor.readthedocs.io/en/latest/settings/#django.conf.settings.COMPRESS_OFFLINE
COMPRESS_OFFLINE = True  # Offline compression is required when using Whitenoise
# https://django-compressor.readthedocs.io/en/latest/settings/#django.conf.settings.COMPRESS_FILTERS
COMPRESS_FILTERS = {
    "css": [
        "compressor.filters.css_default.CssAbsoluteFilter",
        "compressor.filters.cssmin.rCSSMinFilter",
    ],
    "js": ["compressor.filters.jsmin.JSMinFilter"],
}

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s "
            "%(process)d %(thread)d %(message)s"
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "django.db.backends": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
        # Errors logged by the SDK itself
        "sentry_sdk": {"level": "ERROR", "handlers": ["console"], "propagate": False},
        "django.security.DisallowedHost": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

# Sentry
# ------------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN")
SENTRY_KEY = env("SENTRY_KEY")
SENTRY_LOG_LEVEL = env.int("DJANGO_SENTRY_LOG_LEVEL", logging.INFO)

sentry_logging = LoggingIntegration(
    level=SENTRY_LOG_LEVEL,  # Capture info and above as breadcrumbs
    event_level=logging.ERROR,  # Send errors as events
)
integrations = [sentry_logging, DjangoIntegration(), RedisIntegration()]
sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=integrations,
    environment=env("ENV_NAME", default="production"),
    traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
)

# CELERY
CELERY_BROKER_URL = env("DJANGO_CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("DJANGO_CELERY_BROKER_URL")
CELERY_CACHE_BACKEND = "django-cache"


# Your stuff...
# ------------------------------------------------------------------------------

SELF_DECLARATION_FORM_ID = env("DJANGO_SELF_DECLARATION_FORM_ID")

TRANSFER_EVAL_EMAIL_FORM_ID = env("DJANGO_TRANSFER_EVAL_EMAIL_FORM_ID")

ADMIN_OTP_REQUIRED = env.bool("DJANGO_ADMIN_OTP_REQUIRED", default=True)

# This should never be used, it's better to use the more specific `FROM_EMAIL` setting below
# However, in we were to forget to manually set the `from` header in an outgoing email,
# this would be the default value used by Django.
# So it's best to make sure this value stays valid.
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL", default="Envergo <contact@envergo.beta.gouv.fr>"
)

FROM_EMAIL = {
    "amenagement": {
        "default": "Envergo <contact@envergo.beta.gouv.fr>",
        "admin": "Admin Envergo <admin@envergo.beta.gouv.fr>",
        "accounts": "Envergo <comptes@envergo.beta.gouv.fr>",
        "evaluations": "Avis Envergo <avis@envergo.beta.gouv.fr>",
    },
    "haie": {
        "default": "Guichet unique de la haie <contact@haie.beta.gouv.fr>",
        "accounts": "Compte GUH <comptes@haie.beta.gouv.fr>",
    },
}

SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=FROM_EMAIL["amenagement"]["admin"])

# Whenever we are confident the csp policy is ok, move the rules from the "report only"
# settings to this setting.
SECURE_CSP = {}

SECURE_CSP_REPORT_ONLY = {
    "default-src": [CSP.SELF],
    "script-src": [
        CSP.SELF,
        CSP.UNSAFE_INLINE,
        "https://*.crisp.chat",
        "https://sentry.incubateur.net",
        "https://browser.sentry-cdn.com",
        "https://*.data.gouv.fr",
        "https://*.beta.gouv.fr",
    ],
    "connect-src": [
        CSP.SELF,
        "https://*.data.gouv.fr",  # Address autocomplete api
        "https://*.beta.gouv.fr",  # Stats
        "https://sentry.incubateur.net",
        "https://*.crisp.chat",
        "wss://*.relay.crisp.chat",
    ],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE, "https://*.crisp.chat"],
    "img-src": [
        CSP.SELF,
        "https://data.geopf.fr",  # Leaflet geoportail images
        "https://*.s3.fr-par.scw.cloud",
        "data:",
        "https://*.crisp.chat",
    ],
    "font-src": [CSP.SELF, "https://*.crisp.chat"],
    "media-src": [CSP.SELF, "https://*.s3.fr-par.scw.cloud", "https://*.crisp.chat"],
    "frame-src": [CSP.SELF, "https://*.crisp.chat"],
    "worker-src": [CSP.SELF, "blob:", "https://*.crisp.chat"],
    "report-uri": "/csp/reports/",
}

RATELIMIT_IP_META_KEY = "HTTP_X_REAL_IP"
