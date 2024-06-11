from django.contrib.admin.apps import AdminConfig


class EnvergoAdminConfig(AdminConfig):
    default_site = "envergo.admin.site.EnvergoAdminSite"
