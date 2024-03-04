from django.urls import path
from django.utils.translation import gettext_lazy as _

from envergo.geodata.views import CatchmentAreaDebug, ZoneMap, ZoneSearch

urlpatterns = [
    path(_("map/"), ZoneMap.as_view(), name="zone_map"),
    path("demonstrateur-bv/", CatchmentAreaDebug.as_view(), name="2150_debug"),
    path(
        _("zone.geojson"),
        ZoneSearch.as_view(),
        name="zone_search",
    ),
]
