from django.apps import AppConfig


class SecurityConfig(AppConfig):
    """Tracks the known vulnerabilities in the libraries the application runs."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "envergo.security"
