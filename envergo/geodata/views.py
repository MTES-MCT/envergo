import requests
from django.core.serializers import serialize
from django.http import JsonResponse
from django.views.generic import ListView, TemplateView, View
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from envergo.geodata.models import Zone


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


class ZoneData(ListView):
    template_name = "geodata/data.html"
    context_object_name = "data"

    def get_queryset(self):
        qs = Zone.objects.all()[:10]
        data = serialize(
            "geojson", qs, geometry_field="simple_polygon", fields=["code"]
        )
        return data
