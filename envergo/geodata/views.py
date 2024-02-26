import logging

import requests
from django.contrib.gis.geos import GEOSGeometry
from django.core.serializers import serialize
from django.db import connection
from django.http import JsonResponse
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, TemplateView, View
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from envergo.geodata.forms import LatLngForm
from envergo.geodata.models import Zone

logger = logging.getLogger(__name__)


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
        res = requests.get(url)
        json = res.json()

        return json if res.status_code == 200 else None

    def extract_shape(self, json):
        return shape(json["features"][0]["properties"]["trueGeometry"])


class ZoneMap(TemplateView):
    template_name = "geodata/map.html"


@method_decorator(csrf_exempt, name="dispatch")
class ZoneSearch(View):
    def post(self, request, *args, **kwargs):

        geometry = GEOSGeometry(request.body.decode())
        logger.info(geometry)

        qs = Zone.objects.filter(geometry__intersects=geometry)
        data = serialize("geojson", qs, geometry_field="geometry", fields=["code"])
        return HttpResponse(data, content_type="application/json")


class CatchmentAreaDebug(FormView):
    template_name = "geodata/2150_debug.html"
    form_class = LatLngForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = context["form"]
        if form.is_bound and "lng" in form.cleaned_data and "lat" in form.cleaned_data:
            lng, lat = form.cleaned_data["lng"], form.cleaned_data["lat"]
            context["display_marker"] = True
            context["center_map"] = [lng, lat]
            context["default_zoom"] = 16
        else:
            # By default, show all metropolitan france in map
            context["display_marker"] = False
            context["center_map"] = [1.7000, 47.000]
            context["default_zoom"] = 5

        if form.is_bound and "lng" in form.cleaned_data and "lat" in form.cleaned_data:
            lng, lat = form.cleaned_data["lng"], form.cleaned_data["lat"]

            # EPSG_WGS84 = 4326
            # EPSG_MERCATOR = 3857
            # lng_lat = Point(float(lng), float(lat), srid=EPSG_WGS84)
            # coords = lng_lat.transform(EPSG_MERCATOR, clone=True)
            # tiles = CatchmentAreaTile.objects.filter(data__contains=coords)

            with connection.cursor() as cursor:
                query = """
                SELECT ST_Neighborhood(tiles.data, point, 1, 1)
                FROM geodata_catchmentareatile AS tiles
                CROSS JOIN ST_Transform(ST_Point(%s, %s, 4326), 2154) AS point
                WHERE ST_Intersects(tiles.data, point)
                """
                cursor.execute(query, [lng, lat])
                row = cursor.fetchone()
                areas = row[0]
                catchment_area = int(areas[1][1])
                catchment_area_500 = round(catchment_area / 500) * 500
                value_action_requise = max(0, 7000 - catchment_area_500)
                value_soumis = max(0, 12000 - catchment_area_500)

                context["result_available"] = True
                context["areas"] = areas
                context["catchment_area"] = catchment_area
                context["catchment_area_500"] = catchment_area_500
                context["value_action_requise"] = value_action_requise
                context["value_soumis"] = value_soumis

        return context

    def get_initial(self):
        return self.request.GET

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
            "data": self.request.GET,
        }

        return kwargs

    def get(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        form = self.get_form()
        form.is_valid()
        return self.render_to_response(self.get_context_data(form=form))
