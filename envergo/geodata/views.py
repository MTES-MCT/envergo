import logging

import requests
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.serializers import serialize
from django.http import JsonResponse
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from envergo.geodata.models import Zone

logger = logging.getLogger(__name__)


EPSG_WGS84 = 4326
EPSG_LAMB93 = 2154


class ParcelsExport(View):
    """Export a bunch of parcels into geojson"""

    def get(self, request, *args, **kwargs):
        parcels = self.request.GET.getlist("parcel")

        jsons = map(self.get_parcel_json, parcels)
        clean_jsons = filter(None, jsons)
        shapes = map(self.extract_shape, clean_jsons)
        union = unary_union(list(shapes))
        geojson = mapping(union)

        return JsonResponse(geojson)

    def get_parcel_json(self, parcelId):
        """Fetch parcel geometry from IGN api."""

        url = f"https://geocodage.ign.fr/look4/parcel/search?q={parcelId}&returnTrueGeometry=true"
        try:
            res = requests.get(url, timeout=settings.DEFAULT_HTTP_TIMEOUT)
        except requests.exceptions.RequestException as e:
            logger.warning(
                "Error while requesting the IGN parcel geometry api",
                extra={"parcel": parcelId, "exception": e},
            )
            return None

        return res.json() if res.status_code == 200 else None

    def extract_shape(self, json):
        # IGN look4 returns trueGeometry in WGS84; passed through unchanged to
        # the GeoJSON response Leaflet consumes. shapely carries no SRID.
        return shape(json["features"][0]["properties"]["trueGeometry"])


class ZoneMap(TemplateView):
    template_name = "geodata/map.html"


@method_decorator(csrf_exempt, name="dispatch")
class ZoneSearch(View):
    def post(self, request, *args, **kwargs):

        geometry = GEOSGeometry(request.body.decode())
        # Normalize to WGS84 before querying the 4326 geography column: GeoJSON
        # carries no CRS (srid None), and an explicit non-4326 SRID must be
        # reprojected rather than silently compared.
        if geometry.srid is None:
            geometry.srid = EPSG_WGS84
        elif geometry.srid != EPSG_WGS84:
            geometry.transform(EPSG_WGS84)
        logger.info(geometry)

        qs = Zone.objects.filter(geometry__intersects=geometry)
        data = serialize("geojson", qs, geometry_field="geometry", fields=["code"])
        return HttpResponse(data, content_type="application/json")
