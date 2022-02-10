import json

from django.contrib.gis.db.models.functions import Area, Intersection
from django.contrib.gis.geos import GEOSGeometry
from django.core.serializers import serialize
from django.db.models import F, Sum
from model_utils import Choices

from envergo.geodata.models import Zone

RESULTS = Choices(
    ("soumis", "Soumis"),
    ("non-soumis", "Non soumis"),
    ("action-requise", "Action requise"),
)


class Moulinette:
    def __init__(self, data):
        self.data = data

    def run(self):
        footprint_dict = self.data["project_footprint"]
        footprint = GEOSGeometry(json.dumps(footprint_dict), srid=4326)
        footprint.transform(3857)  # mercator projection, to get meter units
        wetlands = (
            Zone.objects
            # .filter(map__data_type="zone_humide")
            .filter(geometry__intersects=footprint)
            .annotate(intersection=Intersection(F("geometry"), footprint))
            .annotate(area=Area("intersection"))
        )
        wetlands_area = wetlands.aggregate(total_area=Sum("area"))["total_area"]

        self.result = {
            "footprint": footprint,
            "wetlands": wetlands,
            "wetlands_area": wetlands_area.sq_m if wetlands_area else 0.0,
        }

    @property
    def footprint_json(self):
        return json.dumps(self.data["project_footprint"])

    @property
    def footprint_surface(self):
        return self.result["footprint"].area

    @property
    def wetlands_json(self):
        wetlands = self.result["wetlands"]
        geojson = serialize("geojson", wetlands, geometry_field="geometry")
        return geojson

    @property
    def eval_result(self):
        return RESULTS.soumis
