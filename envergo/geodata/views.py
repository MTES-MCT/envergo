import logging

import requests
from django.contrib.gis.geos import GEOSGeometry
from django.core.serializers import serialize
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
