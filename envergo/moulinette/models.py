from django.contrib.gis.db.models.functions import Area, Intersection
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
        coords = self.data.get("coords")
        coords.transform(3857)  # mercator projection, to get meter units

        wetlands = (
            Zone.objects
            # .filter(map__data_type="zone_humide")
            .filter(geometry__covers=coords)
            # .annotate(intersection=Intersection(F("geometry"), coords))
            # .annotate(area=Area("intersection"))
        )

        circle_25 = coords.buffer(25)
        wetlands_25 = (
            Zone.objects.filter(geometry__intersects=circle_25)
            .annotate(intersection=Intersection(F("geometry"), coords))
            .annotate(area=Area("intersection"))
        )
        wetlands_area = wetlands_25.aggregate(total_area=Sum("area"))["total_area"]

        circle_100 = coords.buffer(100)
        wetlands_100 = Zone.objects.filter(geometry__intersects=circle_100)

        self.result = {
            "wetlands": wetlands,
            "wetlands_area": wetlands_area.sq_m if wetlands_area else 0.0,
            "circle_25": circle_25,
            "wetlands_25": wetlands_25,
            "circle_100": circle_100,
            "wetlands_100": wetlands_100,
        }

    @property
    def eval_result(self):
        # return RESULTS.soumis
        return "debug"

    @property
    def coords(self):
        coords = self.data["coords"].clone()
        coords.transform(4326)
        return coords

    @property
    def wetlands_json(self):
        wetlands = self.result["wetlands_100"]
        geojson = serialize("geojson", wetlands, geometry_field="geometry")
        return geojson

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
