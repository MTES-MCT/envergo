from django.contrib.gis.geos import Point
from django.core.serializers import serialize
from model_utils import Choices

from envergo.geodata.models import Zone

RESULTS = Choices(
    ("soumis", "Soumis"),
    ("non_soumis", "Non soumis"),
    ("action_requise", "Action requise"),
)


class Moulinette:
    def __init__(self, data):
        self.data = data

    def run(self):
        project_surface = self.data["existing_surface"] + self.data["created_surface"]

        lat = self.data["lat"]
        lng = self.data["lng"]
        # Transform to mercator projection, to get meter units
        coords = Point(float(lng), float(lat), srid=4326).transform(3857, clone=True)

        circle_25 = coords.buffer(25)
        wetlands_25 = (
            Zone.objects
            # .filter(map__data_type="zone_humide")
            .filter(geometry__intersects=circle_25)
        )

        circle_100 = coords.buffer(100)
        wetlands_100 = Zone.objects.filter(geometry__intersects=circle_100)

        self.result = {
            "coords": coords,
            "project_surface": project_surface,
            "circle_25": circle_25,
            "wetlands_25": wetlands_25,
            "wetlands_within_25m": bool(wetlands_25),
            "circle_100": circle_100,
            "wetlands_100": wetlands_100,
            "wetlands_within_100m": bool(wetlands_100),
        }

    @property
    def lat(self):
        return self.data["lat"]

    @property
    def lng(self):
        return self.data["lng"]

    @property
    def eval_result(self):

        if self.result["wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.result["wetlands_within_100m"]:
            wetland_status = "unknown"
        else:
            wetland_status = "outside"

        if self.result["project_surface"] > 1000:
            project_size = "big"
        elif self.result["project_surface"] > 700:
            project_size = "medium"
        else:
            project_size = "small"

        result_matrix = {
            "inside": {
                "big": RESULTS.soumis,
                "medium": RESULTS.action_requise,
                "small": RESULTS.non_soumis,
            },
            "unknown": {
                "big": RESULTS.action_requise,
                "medium": RESULTS.non_soumis,
                "small": RESULTS.non_soumis,
            },
            "outside": {
                "big": RESULTS.non_soumis,
                "medium": RESULTS.non_soumis,
                "small": RESULTS.non_soumis,
            },
        }

        result = result_matrix[wetland_status][project_size]
        return result

    @property
    def result_soumis(self):
        return self.eval_result == RESULTS.soumis

    @property
    def coords(self):
        coords = self.result["coords"]
        return coords

    @property
    def wetlands_json(self):
        wetlands = self.result["wetlands_100"]
        geojson = serialize("geojson", wetlands, geometry_field="geometry")
        return geojson

    @property
    def circle_25_json(self):
        circle = self.result["circle_25"].transform(4326, clone=True)
        return circle.geojson

    @property
    def circle_100_json(self):
        circle = self.result["circle_100"].transform(4326, clone=True)
        return circle.geojson
