import json
import logging
from math import sqrt

import numpy as np
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
from envergo.geodata.utils import get_catchment_area_pixel_values
from envergo.utils.urls import update_qs

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

        current_url = self.request.build_absolute_uri()
        share_btn_url = update_qs(current_url, {"mtm_campaign": "share-demo-bv"})
        context["share_btn_url"] = share_btn_url
        context["debug"] = bool(self.request.GET.get("debug", False))

        form = context["form"]
        if form.is_bound and "lng" in form.cleaned_data and "lat" in form.cleaned_data:
            lng, lat = form.cleaned_data["lng"], form.cleaned_data["lat"]
            context["display_marker"] = True
            context["center_map"] = [lng, lat]
            context["default_zoom"] = 17
        else:
            context["display_marker"] = False
            context["center_map"] = [-4.03177, 48.38986]  # Somewhere in Finistère
            context["default_zoom"] = 8

        context["result_available"] = False
        if form.is_bound and "lng" in form.cleaned_data and "lat" in form.cleaned_data:
            lng, lat = form.cleaned_data["lng"], form.cleaned_data["lat"]

            lng_lat = Point(float(lng), float(lat), srid=EPSG_WGS84)
            lamb93_coords = lng_lat.transform(EPSG_LAMB93, clone=True)

            # Fetch the grid of values to display on the map
            polygons = self.get_pixel_polygons(lng, lat)
            context["polygons"] = json.dumps(polygons)

            # Fetch the envelope that is used to clip raster values
            # (for debug purpose only)
            envelope = self.get_envelope(lng, lat)
            context["envelope"] = json.dumps(envelope)

            pixels = get_catchment_area_pixel_values(lng, lat)
            if not pixels:
                return context

            coords = [(x, y) for x, y, v in pixels]
            values = [int(v) for x, y, v in pixels]
            interpolated_area = griddata(
                coords, values, lamb93_coords, method="linear"
            )[0]
            # If the interpolation fails because of missing data, we don't display anything
            # it should not happen so we don't bother display a real error message
            if np.isnan(interpolated_area):
                return context

            # We get the values as a 1D array, we want to display as a 2D grid
            # for debug purpose
            try:
                values_grid_width = int(sqrt(len(pixels)))
                context["values"] = (
                    np.array(values).reshape(values_grid_width, -1).tolist()
                )
            except ValueError:
                # We are missing data so we can't display a nice grid
                context["flat_values"] = values

            # The value we display is actually rounded to the nearest 500m²
            catchment_area = int(interpolated_area)
            catchment_area_500 = round(catchment_area / 500) * 500

            # Compute values relevant to the moulinette result
            if catchment_area_500 < 9000:
                value_action_requise = max(0, 9000 - catchment_area_500)
                value_soumis = 10000
            else:
                value_action_requise = 500
                value_soumis = 10000

            context["result_available"] = True
            context["catchment_area"] = catchment_area
            context["catchment_area_500"] = catchment_area_500
            context["interpolated_area"] = interpolated_area
            context["value_action_requise"] = value_action_requise
            context["value_soumis"] = value_soumis

        return context

    def get_pixel_polygons(self, lng, lat):
        # This next query only exists to gather data for the map display.
        # We want to display an interactive grid on the map, with a colored based
        # legend.

        # PostGIS provides the handsy ST_PixelAsPolygons, which returns a
        # list of square polygons, each one representing a pixel of the raster.
        # The only subtlety is that for each cell, the actual data points
        # correspond to the top left corner, which is not very intuitive in a
        # visualization. Thus, we have to shift our entire grid so that each cell
        # is centered on the corresponding point.
        polygons = []
        with connection.cursor() as cursor:
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
                        tiles.rast,
                        envelope,
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
                CROSS JOIN
                  ST_Envelope(
                    ST_Buffer(
                      ST_Translate(point, 10, -10),
                      50
                    )
                  ) AS envelope
                WHERE
                  ST_Intersects(tiles.rast, envelope)
              ) gv;
            """
            cursor.execute(query, [lng, lat])
            polygons = cursor.fetchall()
        return polygons

    def get_envelope(self, lng, lat):
        envelope = {}
        with connection.cursor() as cursor:
            query = """
            SELECT
              ST_AsGeoJSON(
                ST_Transform(
                  ST_Envelope(
                    ST_Buffer(point, 50)
                  ),
                  4326
                ))
                FROM
                  ST_Transform(
                    ST_Point(%s, %s, 4326),
                    2154
                  ) AS point;
            """
            cursor.execute(query, [lng, lat])
            envelope = cursor.fetchall()[0]
        return envelope

    def get_initial(self):
        return self.request.GET

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        if "lat" in self.request.GET and "lng" in self.request.GET:
            kwargs["data"] = self.request.GET

        return kwargs

    def get(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        form = self.get_form()
        form.is_valid()
        return self.render_to_response(self.get_context_data(form=form))
