from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig


class ConfsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "envergo.confs"


class EnvergoAdminConfig(AdminConfig):
    default_site = "envergo.confs.admin.EnvergoAdminSite"
