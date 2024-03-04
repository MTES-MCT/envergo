from django.urls import path
from django.utils.translation import gettext_lazy as _

from envergo.geodata.views import ZoneMap, ZoneSearch

urlpatterns = [
    path(_("map/"), ZoneMap.as_view(), name="zone_map"),
    path(
        _("zone.geojson"),
        ZoneSearch.as_view(),
        name="zone_search",
    ),
]
