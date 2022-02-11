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

        circle_25 = footprint.buffer(25)
        wetlands_25 = Zone.objects.filter(geometry__intersects=circle_25)

        circle_100 = footprint.buffer(100)
        wetlands_100 = Zone.objects.filter(geometry__intersects=circle_100)

        self.result = {
            "footprint": footprint,
            "wetlands": wetlands,
            "wetlands_area": wetlands_area.sq_m if wetlands_area else 0.0,
            "circle_25": circle_25,
            "wetlands_25": wetlands_25,
            "circle_100": circle_100,
            "wetlands_100": wetlands_100,
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

    @property
    def circle_25_json(self):
        circle = self.result["circle_25"].clone()
        circle.transform(4326)
        return circle.geojson

    @property
    def circle_100_json(self):
        circle = self.result["circle_100"].clone()
        circle.transform(4326)
        return circle.geojson
