"""
Base settings to build other settings files upon.
"""

from pathlib import Path

import environ

ROOT_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# envergo/
APPS_DIR = ROOT_DIR / "envergo"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(ROOT_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", default=False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "Europe/Paris"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "fr-fr"
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(ROOT_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
# SetUrlConfBasedOnSite middleware will override the urlConf based on the site for a request context
ROOT_URLCONF = "config.urls_amenagement"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # "django.contrib.admin",  # it's overriden below
    "django.forms",
    "django.contrib.gis",
    "django.contrib.sitemaps",
]
THIRD_PARTY_APPS = [
    "phonenumber_field",
    "leaflet",
    "localflavor",
    "django_otp",
    "django_otp.plugins.otp_totp",
]

LOCAL_APPS = [
    "envergo.contrib",
    "envergo.users.apps.UsersConfig",
    "envergo.pages",
    "envergo.evaluations",
    "envergo.geodata",
    "envergo.stats",
    "envergo.moulinette",
    "envergo.analytics",
    "envergo.confs.apps.ConfsConfig",
    "envergo.admin.config.EnvergoAdminConfig",
    "envergo.urlmappings",
    "envergo.hedges",
    "envergo.petitions",
    "envergo.demos",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "envergo.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "envergo.users.backends.AuthBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "home"
AMENAGEMENT_LOGIN_REDIRECT_URL = "home"
HAIE_LOGIN_REDIRECT_URL = "petition_project_list"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "login"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "envergo.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # "django.middleware.common.BrokenLinkEmailsMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "envergo.contrib.middleware.SetUrlConfBasedOnSite",
    "envergo.analytics.middleware.SetVisitorIdCookie",
    "envergo.middleware.rate_limiting.RateLimitingMiddleware",
    "envergo.analytics.middleware.HandleMtmValues",
    "envergo.petitions.middleware.HandleInvitationTokenMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(ROOT_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static"), str(ROOT_DIR / "node_modules")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#template-dirs
        "DIRS": [str(APPS_DIR / "templates")],
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-loaders
            # https://docs.djangoproject.com/en/dev/ref/templates/api/#loader-types
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "envergo.utils.context_processors.settings_context",
                "envergo.utils.context_processors.multi_sites_context",
                "envergo.utils.context_processors.newsletter_context",
                "envergo.analytics.context_processors.analytics",
                "envergo.analytics.context_processors.visitor_id",
                "envergo.evaluations.context_processors.request_eval_context",
            ],
        },
    }
]
# https://github.com/jazzband/django-debug-toolbar/issues/1550
SILENCED_SYSTEM_CHECKS = ["debug_toolbar.W006"]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap4"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-browser-xss-filter
SECURE_BROWSER_XSS_FILTER = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [x.split(":") for x in env.list("DJANGO_ADMINS", default=[])]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
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
}


# django-compressor
# ------------------------------------------------------------------------------
# https://django-compressor.readthedocs.io/en/latest/quickstart/#installation
INSTALLED_APPS += ["compressor"]
STATICFILES_FINDERS += ["compressor.finders.CompressorFinder"]

# Handle file uploads
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
    "upload": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

# CELERY
if USE_TZ:
    CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_URL = env("DJANGO_CELERY_BROKER_URL", default="memory://localhost/")
CELERY_RESULT_BACKEND = "cache"
CELERY_CACHE_BACKEND = "memory"
CELERY_TASK_ALWAYS_EAGER = False
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True


SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_KEY = env("SENTRY_KEY", default="")


# Your stuff...
# ------------------------------------------------------------------------------

ANALYTICS = {
    "AMENAGEMENT": {
        "TRACKER_ENABLED": env("DJANGO_AMENAGEMENT_TRACKER_ENABLED", default=False),
        "TRACKER_URL": env("DJANGO_AMENAGEMENT_TRACKER_URL", default=""),
        "SITE_ID": env("DJANGO_AMENAGEMENT_SITE_ID", default=""),
        "SECURITY_TOKEN": env("DJANGO_AMENAGEMENT_MATOMO_SECURITY_TOKEN", default=""),
    },
    "HAIE": {
        "TRACKER_ENABLED": env("DJANGO_HAIE_TRACKER_ENABLED", default=False),
        "TRACKER_URL": env("DJANGO_HAIE_TRACKER_URL", default=""),
        "SITE_ID": env("DJANGO_HAIE_SITE_ID", default=""),
        "SECURITY_TOKEN": env("DJANGO_HAIE_MATOMO_SECURITY_TOKEN", default=""),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

PHONENUMBER_DEFAULT_REGION = "FR"

LEAFLET_CONFIG = {
    "TILES": "http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "DEFAULT_CENTER": (47, 1.7),
    "DEFAULT_ZOOM": 6,
    "MIN_ZOOM": 5,
    "MAX_ZOOM": 19,
}

ENVERGO_REFERENCE_LENGTH = 6

URLMAPPING_KEY_LENGTH = 6

VISITOR_COOKIE_NAME = "visitorid"

# The max number of files that can be uploaded with a single evaluation request
MAX_EVALREQ_FILES = 25
MAX_EVALREQ_FILESIZE = 50

TEST_EMAIL = "test@test.fr"


# Third party integration settings

MATTERMOST_ENDPOINT_AMENAGEMENT = env("DJANGO_MATTERMOST_ENDPOINT", default=None)
MATTERMOST_ENDPOINT_HAIE = env("DJANGO_MATTERMOST_ENDPOINT_HAIE", default=None)

NOTION_SECRET = env("DJANGO_NOTION_SECRET", default=None)
NOTION_DATABASE_ID = env("DJANGO_NOTION_DATABASE_ID", default=None)

MATOMO_EVALREQ_DIMENSION_ID = 1
MATOMO_SIMULATION_DIMENSION_ID = 2

CRISP = {
    "AMENAGEMENT": {
        "CHATBOX_ENABLED": env("DJANGO_CRISP_CHATBOX_ENABLED", default=False),
        "WEBSITE_ID": env("DJANGO_CRISP_WEBSITE_ID", default=None),
    },
    "HAIE": {
        "CHATBOX_ENABLED": env("DJANGO_CRISP_HAIE_CHATBOX_ENABLED", default=False),
        "WEBSITE_ID": env("DJANGO_CRISP_HAIE_WEBSITE_ID", default=None),
    },
}

SELF_DECLARATION_FORM_ID = "mDzXgX"

TRANSFER_EVAL_EMAIL_FORM_ID = "mDzXgX"

ADMIN_OTP_REQUIRED = False

GEOMETRICIAN_WEBINAR_FORM_URL = env(
    "DJANGO_GEOMETRICIAN_WEBINAR_FORM_URL",
    default="https://app.livestorm.co/p/3e2db81a-a8eb-4684-83e9-9ba999f8bb37/form",
)

# Make.com integration settings
MAKE_COM_WEBHOOK = env(
    "DJANGO_MAKE_COM_WEBHOOK", default=None
)  # webhook for new evaluation requests

MAKE_COM_EVALUATION_EDITION_WEBHOOK = env(
    "DJANGO_MAKE_COM_EVALUATION_EDITION_WEBHOOK",
    default=None,  # webhook for edited evaluations
)


ENVERGO_AMENAGEMENT_DOMAIN = env(
    "DJANGO_ENVERGO_AMENAGEMENT_DOMAIN", default="envergo.beta.gouv.fr"
)
ENVERGO_HAIE_DOMAIN = env("DJANGO_ENVERGO_HAIE_DOMAIN", default="haie.beta.gouv.fr")

DEMARCHES_SIMPLIFIEES = {
    # Documentation API de pré-remplissage :
    # https://doc.demarches-simplifiees.fr/pour-aller-plus-loin/api-de-preremplissage
    "ENABLED": env("DJANGO_DEMARCHES_SIMPLIFIEES_ENABLED", default=False),
    "DOSSIER_BASE_URL": "https://www.demarches-simplifiees.fr",
    "PRE_FILL_API_URL": env(
        "DJANGO_DEMARCHE_SIMPLIFIE_PRE_FILL_API_URL",
        default="https://www.demarches-simplifiees.fr/api/public/v1/",
    ),
    "GRAPHQL_API_URL": env(
        "DJANGO_DEMARCHE_SIMPLIFIE_GRAPHQL_API_URL",
        default="https://www.demarches-simplifiees.fr/api/v2/graphql",
    ),
    "GRAPHQL_API_BEARER_TOKEN": env("DJANGO_DEMARCHE_SIMPLIFIEE_TOKEN", default=None),
    "DOSSIER_DOMAIN_BLACK_LIST": env.list(
        "DJANGO_DOSSIER_DOMAIN_BLACK_LIST", default=[]
    ),
    "INSTRUCTEUR_ID": env("DJANGO_DEMARCHE_SIMPLIFIEE_INSTRUCTEUR_ID", default=None),
}

OPS_MATTERMOST_HANDLERS = env.list("DJANGO_OPS_MATTERMOST_HANDLERS", default=[])
CONFIG_MATTERMOST_HANDLERS = env.list("DJANGO_CONFIG_MATTERMOST_HANDLERS", default=[])

BREVO = {
    "API_URL": env("BREVO_API_URL", default="https://api.brevo.com/v3/"),
    "API_KEY": env("BREVO_API_KEY", default=None),
    "NEWSLETTER_LISTS": {
        "instructeur": env("BREVO_NEWSLETTER_LIST_INSTRUCTEUR", default=None),
        "amenageur": env("BREVO_NEWSLETTER_LIST_AMENAGEUR", default=None),
        "geometre": env("BREVO_NEWSLETTER_LIST_GEOMETRE", default=None),
        "bureau": env("BREVO_NEWSLETTER_LIST_BUREAU", default=None),
        "architecte": env("BREVO_NEWSLETTER_LIST_ARCHITECTE", default=None),
        "particulier": env("BREVO_NEWSLETTER_LIST_PARTICULIER", default=None),
        "autre": env("BREVO_NEWSLETTER_LIST_AUTRE", default=None),
    },
    "NEWSLETTER_DOUBLE_OPT_IN_TEMPLATE_ID": env(
        "BREVO_NEWSLETTER_DOUBLE_OPT_IN_TEMPLATE_ID", default=None
    ),
}

GUH_DATA_EXPORT_TEMPLATE = APPS_DIR.joinpath(
    "static/gpkg/hedge_data_export_template.gpkg"
)

FROM_EMAIL = {
    "amenagement": {
        "default": "contact@amenagement.local",
        "admin": "admin@amenagement.local",
        "accounts": "comptes@amenagement.local",
        "evaluations": "avis@amenagement.local",
    },
    "haie": {
        "default": "contact@haie.local",
        "accounts": "comptes@haie.local",
    },
}

HAIE_FAQ_URLS = {
    "SERVICE_USERS": "https://equatorial-red-4c6.notion.site/Guichet-unique-de-la-haie-Ressources-pour-les-usagers-17efe5fe47668058a991eb26153a70b0",  # noqa: E501
    "INSTRUCTORS": "https://equatorial-red-4c6.notion.site/Guichet-unique-de-la-haie-Ressources-pour-les-services-instructeurs-17afe5fe476680aebd08f47929bb0718",  # noqa: E501
    "BEST_ENVIRONMENTAL_LOCATION_ORGANIZATIONS_LIST": "https://equatorial-red-4c6.notion.site/Liste-des-organismes-agr-s-pour-d-livrer-une-attestation-de-meilleur-emplacement-environnemental-2e9fe5fe47668150a8a1f57c2e44f44e",  # noqa: E501
    "TREE_SPECIES_COPPICING_CAPACITY": "https://equatorial-red-4c6.notion.site/Liste-des-essences-et-leur-capacit-rec-per-2e9fe5fe476681568c89f296be4bfc02",  # noqa: E501
    "FIVE_HEDGES_TYPES": "https://equatorial-red-4c6.notion.site/Les-cinq-types-de-haies-2e9fe5fe476681fabfb4f45300d54a7f",  # noqa: E501
    "NORMANDIE_HEDGES_FOR_COMPENSATION_REDUCTION": "https://equatorial-red-4c6.notion.site/Normandie-quels-types-de-haie-permettent-une-r-duction-de-la-compensation-attendue-2e9fe5fe47668120bdd6ec6fd14a6195",  # noqa: E501
    "NORMANDIE_EP_FOR_WORKS": "https://equatorial-red-4c6.notion.site/Normandie-prise-en-compte-des-esp-ces-prot-g-es-pour-les-demandes-de-travaux-sur-haies-2e9fe5fe4766819bb55af564fd39b782",  # noqa: E501
    "IDENTIFY_NATURAL_AREA_MANAGER": "https://equatorial-red-4c6.notion.site/Comment-identifier-une-r-serve-naturelle-et-son-gestionnaire-2e9fe5fe476681608770efde43cf92c8",  # noqa: E501
    "GUIDE_FORM_HEDGE_DESTRUCTION": "https://equatorial-red-4c6.notion.site/Guide-au-remplissage-du-formulaire-de-d-claration-pr-alable-pour-une-destruction-de-haie-ou-d-aligne-2e9fe5fe47668173a2a1d4b83630a750",  # noqa: E501
    "IDENTIFY_PROTECTIONS_HEDGES_AA_IN_GEOPORTAIL": "https://equatorial-red-4c6.notion.site/Comment-identifier-les-protections-sur-les-haies-et-alignements-d-arbres-dans-le-g-oportail-de-l-urb-2e9fe5fe47668126ba11eb2e1c74e6a6",  # noqa: E501
}

# Temporary deactivate the InMemoryUploadFileHandler because it crashes the map upload
FILE_UPLOAD_HANDLERS = [
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]

SECURE_CSP = {}

SECURE_CSP_REPORT_ONLY = {}

RATELIMIT_RATE = "100/m"

INVITATION_TOKEN_COOKIE_NAME = "invitation_token"

DISPLAY_TEACHING_TOPBAR = env.bool("DJANGO_DISPLAY_TEACHING_TOPBAR", default=False)

HASH_SALT_KEY = "123abc"
