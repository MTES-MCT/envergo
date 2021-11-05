from django.urls import path
from django.utils.translation import gettext_lazy as _

from envergo.geodata.views import ZoneData, ZoneMap

urlpatterns = [
    path(_("map/"), ZoneMap.as_view(), name="zone_map"),
    path(
        _("map/<int:z>/<int:x>/<int:y>.geojson"),
        ZoneData.as_view(),
        name="zone_data",
    ),
]
