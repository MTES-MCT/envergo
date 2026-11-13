from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SecurityConfig(AppConfig):
    """Tracks the known vulnerabilities in the libraries the application runs."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "envergo.security"
    verbose_name = _("Security")
