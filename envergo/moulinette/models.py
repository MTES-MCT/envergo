from django.contrib.gis.geos import Point
from django.core.serializers import serialize
from model_utils import Choices

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import Department, Zone


def fetch_zones_around(coords, radius, zone_type):
    """Helper method to fetch Zones around a given point."""

    circle = coords.buffer(radius)
    qs = Zone.objects.filter(map__data_type=zone_type).filter(
        geometry__intersects=circle
    )
    return qs


# Those dummy methods are useful for unit testing
def fetch_wetlands_around_25m(coords):
    return fetch_zones_around(coords, 25, "zone_humide")


def fetch_wetlands_around_100m(coords):
    return fetch_zones_around(coords, 100, "zone_humide")


def fetch_flood_zones_around_12m(coords):
    return fetch_zones_around(coords, 12, "zone_inondable")


class Moulinette:
    """Automatic water law processing tool.

    Given a bunch of relevant user provided data, we try to perform an
    automatic computation and tell if the project is subject to the Water Law.
    """

    def __init__(self, data):
        self.data = data

    def run(self):
        project_surface = self.data["existing_surface"] + self.data["created_surface"]
        lng = self.data["lng"]
        lat = self.data["lat"]
        lngLat = Point(float(lng), float(lat), srid=4326)
        department = Department.objects.filter(geometry__contains=lngLat).first()

        # Transform to mercator projection, to get meter units
        coords = lngLat.transform(3857, clone=True)

        # Fetch data for the 3.3.1.0 criteria ("Zones humides")
        wetlands_25 = fetch_wetlands_around_25m(coords)
        wetlands_100 = fetch_wetlands_around_100m(coords)

        # Fetch data for the 3.2.2.0 criteria ("Lit majeur")
        flood_zones_12 = fetch_flood_zones_around_12m(coords)

        # Useful debug data
        circle_12 = coords.buffer(12)
        circle_25 = coords.buffer(25)
        circle_100 = coords.buffer(100)

        self.result = {
            "coords": coords,
            "department": department,
            "project_surface": project_surface,
            "wetlands_25": wetlands_25,
            "wetlands_within_25m": bool(wetlands_25),
            "wetlands_100": wetlands_100,
            "wetlands_within_100m": bool(wetlands_100),
            "flood_zones_12": flood_zones_12,
            "flood_zones_within_12m": bool(flood_zones_12),
            "circle_12": circle_12,
            "circle_25": circle_25,
            "circle_100": circle_100,
        }

    @property
    def lat(self):
        return self.data["lat"]

    @property
    def lng(self):
        return self.data["lng"]

    @property
    def department(self):
        return self.result["department"]

    @property
    def eval_result_3310(self):
        """Run the check for the 3.3.1.0 rule."""

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
                "big": RESULTS.action_requise,
                "medium": RESULTS.non_soumis,
                "small": RESULTS.non_soumis,
            },
        }
        result = result_matrix[wetland_status][project_size]
        return result

    @property
    def eval_result_3220(self):
        """Run the check for the 3.1.2.0 rule."""

        if self.result["flood_zones_within_12m"]:
            flood_zone_status = "inside"
        else:
            flood_zone_status = "outside"

        if self.result["project_surface"] > 400:
            project_size = "big"
        elif self.result["project_surface"] > 350:
            project_size = "medium"
        else:
            project_size = "small"

        result_matrix = {
            "inside": {
                "big": RESULTS.soumis,
                "medium": RESULTS.action_requise,
                "small": RESULTS.non_soumis,
            },
            "outside": {
                "big": RESULTS.non_soumis,
                "medium": RESULTS.non_soumis,
                "small": RESULTS.non_soumis,
            },
        }

        result = result_matrix[flood_zone_status][project_size]
        return result

    @property
    def eval_result(self):
        """Combine results of the different checks to produce a full evaluation."""

        department = self.result["department"]
        contact_info = getattr(department, "contact_md", None)
        if not contact_info:
            return RESULTS.nd

        result_3310 = self.eval_result_3310
        result_3220 = self.eval_result_3220
        results = [result_3310, result_3220]

        if RESULTS.soumis in results:
            result = RESULTS.soumis
        elif RESULTS.action_requise in results:
            result = RESULTS.action_requise
        else:
            result = RESULTS.non_soumis

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
    def flood_zones_json(self):
        flood_zones = self.result["flood_zones_12"]
        geojson = serialize("geojson", flood_zones, geometry_field="geometry")
        return geojson

    @property
    def circle_12_json(self):
        circle = self.result["circle_12"].transform(4326, clone=True)
        return circle.geojson

    @property
    def circle_25_json(self):
        circle = self.result["circle_25"].transform(4326, clone=True)
        return circle.geojson

    @property
    def circle_100_json(self):
        circle = self.result["circle_100"].transform(4326, clone=True)
        return circle.geojson
