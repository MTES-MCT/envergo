from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class GeodataConfig(AppConfig):
    name = "envergo.geodata"
    verbose_name = _("Geo data")
