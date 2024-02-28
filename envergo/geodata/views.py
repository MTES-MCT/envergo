import json
import logging

import requests
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.serializers import serialize
from django.db import connection
from django.http import JsonResponse
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, TemplateView, View
from scipy.interpolate import griddata
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from envergo.geodata.forms import LatLngForm
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

            lng_lat = Point(float(lng), float(lat), srid=EPSG_WGS84)
            lamp93_coords = lng_lat.transform(EPSG_LAMB93, clone=True)

            with connection.cursor() as cursor:
                # It took me a week to come up with the following queries, so here is
                # a bit of explanation.

                # In the database, we have a raster storing catchment area values for
                # various coordinates, arranged in a 20x20m grid, and stored in a
                # Lambert93 projection.
                # The user provides a lat/lng coordinate, and we want to know the
                # catchment area at this point.

                # Here is the catch: we don't just want to get the nearest value, since
                # there can be huge variations from one cell to the other.
                # So we have to use bilinear interpolaton to "smooth" the values.

                # I couldn't find a way to do this directly in PostGIS, so the actual
                # interpolation has to be performed in Python. It means we need to
                # fetch a grid of coordinates / values around the point from the db.

                # The usual raster querying methods ST_Value, ST_NearestValue and
                # ST_Neighborhood return value from the raster, but not the coordinates.
                # So we have to use the alternative ST_PixelAsPoints, which converts
                # the raster values into Point geometries, alongside the associated values.

                # To only get the relevant values, we clip the raster with a bounding box
                # around our point using ST_Clip(ST_Envelope(ST_Buffer(…

                query = """
                SELECT ST_X(geom), ST_Y(geom), val
                FROM (
                  SELECT
                    (ST_PixelAsPoints(
                      ST_Clip(
                        tiles.data,
                        ST_Envelope(
                          ST_Buffer(point, 30)
                        )
                      )
                  )).*
                  FROM
                    geodata_catchmentareatile AS tiles
                    CROSS JOIN
                      ST_Transform(
                        ST_Point(%s, %s, 4326),
                        2154
                    ) AS point
                  WHERE
                    ST_Intersects(tiles.data, point)
                  ) points;
                """
                cursor.execute(query, [lng, lat])
                pixels = cursor.fetchall()
                coords = [(x, y) for x, y, v in pixels]
                values = [v for x, y, v in pixels]
                interpolated_area = griddata(
                    coords, values, lamp93_coords, method="cubic"
                )[0]

                # The value we display is actually rounded to the nearest 500m²
                catchment_area = int(interpolated_area)
                catchment_area_500 = round(catchment_area / 500) * 500

                # Compute values relevant to the moulinette result
                value_action_requise = max(0, 7000 - catchment_area_500)
                value_soumis = max(0, 12000 - catchment_area_500)

                # This next query only exists to gather data for the map display.
                # We want to display an interactive grid on the map, with a colored based
                # legend.

                # PostGIS provides the handsy ST_PixelAsPolygons, which returns a
                # list of square polygons, each one representing a pixel of the raster.
                # The only subtlety is that for each cell, the actual data points
                # correspond to the top left corner, which is not very intuitive in a
                # visualization. Thus, we have to shift our entire grid so that each cell
                # is centered on the corresponding point.
                query = """
                SELECT
                  (gv).x,
                  (gv).y,
                  (gv).val,
                  ST_AsGeoJSON(
                    ST_Transform(
                      ST_Translate(
                        (gv).geom,
                        -10, 10
                      ),
                      4326
                    )
                  ) geom
                FROM
                  (
                    SELECT
                      (
                        ST_PixelAsPolygons(
                          ST_Clip(
                            tiles.data,
                            ST_Envelope(
                              ST_Buffer(
                                ST_Translate(point, 10, -10),
                                50
                              )
                            ),
                            false
                          )
                        )
                      ).*
                    FROM
                      geodata_catchmentareatile AS tiles
                    CROSS JOIN
                      ST_Transform(
                        ST_Point(%s, %s, 4326),
                        2154
                      ) AS point
                    WHERE
                      ST_Intersects(tiles.data, point)
                  ) gv;
                """
                cursor.execute(query, [lng, lat])
                polygons = cursor.fetchall()

                context["result_available"] = True
                context["catchment_area"] = catchment_area
                context["catchment_area_500"] = catchment_area_500
                context["interpolated_area"] = interpolated_area
                context["value_action_requise"] = value_action_requise
                context["value_soumis"] = value_soumis
                context["polygons"] = json.dumps(polygons)

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
