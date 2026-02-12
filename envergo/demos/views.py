import json
from math import sqrt

import numpy as np
from django.contrib.gis.geos import MultiLineString, Point
from django.db import connection
from django.views.generic import FormView
from scipy.interpolate import griddata

from envergo.geodata.forms import LatLngForm
from envergo.geodata.models import MAP_TYPES, Line
from envergo.geodata.utils import (
    compute_hedge_density_around_point,
    get_catchment_area_pixel_values,
    to_geojson,
)
from envergo.hedges.forms import HedgeForm
from envergo.utils.urls import remove_mtm_params, update_qs

EPSG_WGS84 = 4326
EPSG_LAMB93 = 2154


class LatLngDemoMixin:
    mtm_campaign_tag = "demos"
    default_lng_lat = [-4.03177, 48.38986]  # Finistère

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        current_url = self.request.build_absolute_uri()
        share_btn_url = update_qs(
            remove_mtm_params(current_url), {"mtm_campaign": self.mtm_campaign_tag}
        )
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
            context["center_map"] = self.default_lng_lat
            context["default_zoom"] = 8

        form = context["form"]
        context["result_available"] = False
        if form.is_bound and "lng" in form.cleaned_data and "lat" in form.cleaned_data:
            lng, lat = form.cleaned_data["lng"], form.cleaned_data["lat"]
            context.update(self.get_result_data(lng, lat))

        return context


class HedgeDensity(LatLngDemoMixin, FormView):
    template_name = "demos/hedge_density.html"
    form_class = LatLngForm
    mtm_campaign_tag = "share-demo-densite-haie"
    default_lng_lat = [-0.274314, 49.276204]

    def get_result_data(self, lng, lat):
        """Return context with data to display map"""
        lng_lat = Point(float(lng), float(lat), srid=EPSG_WGS84)
        density_200 = compute_hedge_density_around_point(lng_lat, 200)
        density_400 = compute_hedge_density_around_point(lng_lat, 400)
        density_5000 = compute_hedge_density_around_point(lng_lat, 5000)

        circle = (
            density_5000["artifacts"]["truncated_circle"]
            or density_5000["artifacts"]["circle"]
        )

        hedges_5000 = Line.objects.filter(
            map__map_type=MAP_TYPES.haies,
            geometry__intersects=circle,
        )

        hedges_5000_mls = []
        for hedge in hedges_5000:
            geom = hedge.geometry
            if geom:
                hedges_5000_mls.extend(geom)

        polygons = []
        polygons.append(
            {
                "polygon": to_geojson(
                    MultiLineString(hedges_5000_mls, srid=EPSG_WGS84)
                ),
                "color": "#f0f921",
                "legend": "Haies",
                "opacity": 1.0,
            }
        )
        polygons.append(
            {
                "polygon": to_geojson(
                    density_200["artifacts"]["truncated_circle"]
                    or density_200["artifacts"]["circle"]
                ),
                "color": "#f89540",
                "legend": "200m",
                "opacity": 1.0,
            }
        )
        polygons.append(
            {
                "polygon": to_geojson(
                    density_400["artifacts"]["truncated_circle"]
                    or density_400["artifacts"]["circle"]
                ),
                "color": "#cc4778",
                "legend": "400m",
                "opacity": 1.0,
            }
        )
        polygons.append(
            {
                "polygon": to_geojson(
                    density_5000["artifacts"]["truncated_circle"]
                    or density_5000["artifacts"]["circle"]
                ),
                "color": "#7e03a8",
                "legend": "5km",
                "opacity": 1.0,
            }
        )
        context = {
            "result_available": True,
            "length_200": density_200["artifacts"]["length"],
            "area_200_ha": density_200["artifacts"]["area_ha"],
            "truncated_circle_200": density_200["artifacts"]["truncated_circle"],
            "density_200": density_200["density"],
            "length_400": density_400["artifacts"]["length"],
            "area_400_ha": density_400["artifacts"]["area_ha"],
            "truncated_circle_400": density_400["artifacts"]["truncated_circle"],
            "density_400": density_400["density"],
            "length_5000": density_5000["artifacts"]["length"],
            "area_5000_ha": density_5000["artifacts"]["area_ha"],
            "truncated_circle_5000": density_5000["artifacts"]["truncated_circle"],
            "density_5000": density_5000["density"],
            "polygons": json.dumps(polygons),
        }
        return context


class HedgeDensityBuffer(LatLngDemoMixin, FormView):
    """Displays hedge density inside a buffer around a hedge data given in query string"""

    template_name = "demos/hedge_density_buffer.html"
    form_class = HedgeForm
    mtm_campaign_tag = "share-demo-densite-haie"

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        if "haies" in self.request.GET:
            kwargs["data"] = self.request.GET

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = context["form"]
        if form.is_bound and "haies" in form.cleaned_data:
            hedges = form.cleaned_data["haies"]
            centroid = hedges.get_centroid_to_remove()
            context["display_marker"] = True
            context["center_map"] = [centroid.x, centroid.y]
            context["default_zoom"] = 17
        else:
            context["display_marker"] = False
            context["center_map"] = self.default_lng_lat
            context["default_zoom"] = 8

        form = context["form"]
        context["result_available"] = False
        if form.is_bound and "haies" in form.cleaned_data:
            hedges = form.cleaned_data["haies"]
            context.update(self.get_result_data(hedges))

        return context

    def get_result_data(self, hedges):
        """Return context with data to display map"""

        # Create multilinestring from hedges to remove
        hedges_to_remove_mls = []
        for hedge in hedges.hedges_to_remove():
            geom = MultiLineString(hedge.geos_geometry)
            if geom:
                hedges_to_remove_mls.extend(geom)

        polygons = []
        polygons.append(
            {
                "polygon": to_geojson(
                    MultiLineString(hedges_to_remove_mls, srid=EPSG_WGS84)
                ),
                "color": "red",
                "legend": "Haies à détruire",
                "opacity": 1.0,
            }
        )
        context = {
            "result_available": True,
            "hedges_to_remove_mls": hedges_to_remove_mls,
            "polygons": json.dumps(polygons),
        }
        return context


class CatchmentArea(LatLngDemoMixin, FormView):
    template_name = "demos/catchment_area.html"
    form_class = LatLngForm
    mtm_campaign_tag = "share-demo-bv"

    def get_result_data(self, lng, lat):
        context = {}
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
        interpolated_area = griddata(coords, values, lamb93_coords, method="linear")[0]
        # If the interpolation fails because of missing data, we don't display anything
        # it should not happen so we don't bother display a real error message
        if np.isnan(interpolated_area):
            return context

        # We get the values as a 1D array, we want to display as a 2D grid
        # for debug purpose
        try:
            values_grid_width = int(sqrt(len(pixels)))
            context["values"] = np.array(values).reshape(values_grid_width, -1).tolist()
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
