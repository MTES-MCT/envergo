from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance as D
from django.db import models
from django.db.models import F
from django.db.models.functions import Cast
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Department, Zone
from envergo.moulinette.fields import CriterionChoiceField
from envergo.moulinette.regulations.evalenv import EvalEnvironnementale
from envergo.moulinette.regulations.loisurleau import LoiSurLEau
from envergo.moulinette.regulations.natura2000 import Natura2000

# WGS84, geodetic coordinates, units in degrees
# Good for storing data and working wordwide
EPSG_WGS84 = 4326

# Projected coordinates
# Used for displaying tiles in web map systems (OSM, GoogleMaps)
# Good for working in meters
EPSG_MERCATOR = 3857


def fetch_zones_around(coords, radius, zone_type, data_certainty="certain"):
    """Helper method to fetch Zones around a given point."""

    qs = (
        Zone.objects.filter(map__data_type=zone_type)
        .filter(geometry__dwithin=(coords, D(m=radius)))
        .filter(map__data_certainty=data_certainty)
    )
    return qs


# Those dummy methods are useful for unit testing
def fetch_wetlands_around_25m(coords):
    return fetch_zones_around(coords, 25, "zone_humide")


def fetch_wetlands_around_100m(coords):
    return fetch_zones_around(coords, 100, "zone_humide")


def fetch_potential_wetlands(coords):
    qs = (
        Zone.objects.filter(map__data_type="zone_humide")
        .filter(map__data_certainty="uncertain")
        .filter(geometry__dwithin=(coords, D(m=0)))
    )
    return qs


def fetch_flood_zones_around_12m(coords):
    return fetch_zones_around(coords, 12, "zone_inondable")


class Perimeter(models.Model):
    """Link a map and regulation criteria."""

    name = models.CharField(_("Name"), max_length=256)
    map = models.ForeignKey(
        "geodata.Map",
        verbose_name=_("Map"),
        related_name="perimeters",
        on_delete=models.PROTECT,
    )
    criterion = CriterionChoiceField(_("Criterion"))
    activation_distance = models.PositiveIntegerField(
        _("Activation distance"), default=0
    )

    class Meta:
        verbose_name = _("Perimeter")
        verbose_name_plural = _("Perimeters")

    def __str__(self):
        return self.name


class MoulinetteCatalog(dict):
    """Custom class responsible for fetching data used in regulation evaluations.

    The catalog is passed to Regulation and Criterion objects, and those objects
    can contribute data to the dictionary.

    But some data is used in several criterions, so it must be fetched beforehand.
    """

    def __missing__(self, key):
        """If the data is not in the dict, use a method to fetch it."""

        if not hasattr(self, key):
            raise KeyError()

        method = getattr(self, key)
        value = method()
        self[key] = value
        return value


class Moulinette:
    """Automatic environment law evaluation processing tool.

    Given a bunch of relevant user provided data, we try to perform an
    automatic computation and tell if the project is subject to the Water Law
    or other regulations.
    """

    def __init__(self, data, raw_data):
        self.raw_data = raw_data
        self.catalog = MoulinetteCatalog(**data)
        self.catalog.update(self.get_catalog_data())
        self.perimeters = self.get_perimeters()
        self.criterions = set([perimeter.criterion for perimeter in self.perimeters])

        # This is a clear case of circular references, since the Moulinette
        # holds references to the regulations it's computing, but regulations and
        # criterions holds a reference to the Moulinette.
        # That is because the Reality™ is messy and sometimes criterions require
        # access to other pieces of data from the moulinette.
        # For example, to compute the "Natura2000" result, there is a criterion
        # that is just the result of the "Loi sur l'eau" regulation.
        self.regulations = [
            LoiSurLEau(self),
            Natura2000(self),
            EvalEnvironnementale(self),
        ]

        self.catalog.update(self.cleaned_additional_data())

    def get_catalog_data(self):
        """Fetch / compute data required for further computations."""

        lng = self.catalog["lng"]
        lat = self.catalog["lat"]
        lng_lat = Point(float(lng), float(lat), srid=EPSG_WGS84)

        catalog = {}
        catalog["project_surface"] = (
            self.catalog["existing_surface"] + self.catalog["created_surface"]
        )

        catalog["coords"] = lng_lat.transform(EPSG_MERCATOR, clone=True)
        catalog["department"] = Department.objects.filter(
            geometry__contains=lng_lat
        ).first()
        catalog["circle_12"] = catalog["coords"].buffer(12)
        catalog["circle_25"] = catalog["coords"].buffer(25)
        catalog["circle_100"] = catalog["coords"].buffer(100)

        zones = (
            Zone.objects.filter(geometry__dwithin=(catalog["coords"], D(m=500)))
            .annotate(distance=Distance("geometry", catalog["coords"]))
            .annotate(geom=Cast("geometry", MultiPolygonField()))
            .select_related("map")
        )
        catalog['all_zones'] = zones

        def wetlands_filter(zone):
            return all(
                (
                    zone.map.data_type == "zone_humide",
                    zone.map.data_certainty == "certain",
                )
            )
        catalog["wetlands"] = list(filter(wetlands_filter, zones))

        def potential_wetlands_filter(zone):
            return all(
                (
                    zone.map.data_type == "zone_humide",
                    zone.map.data_certainty == "uncertain",
                )
            )
        catalog["potential_wetlands"] = list(filter(potential_wetlands_filter, zones))

        def flood_zones_filter(zone):
            return all(
                (
                    zone.map.data_type == "zone_inondable",
                    zone.map.data_certainty == "certain",
                )
            )
        catalog["flood_zones"] = list(filter(flood_zones_filter, zones))

        return catalog

    def get_perimeters(self):
        """Find activated perimeters

        Regulation criterions have a geographical component and must only computed in
        certain zones.
        """
        coords = self.catalog["coords"]
        perimeters = (
            Perimeter.objects.filter(
                map__zones__geometry__dwithin=(coords, F("activation_distance"))
            )
            .annotate(geometry=F("map__zones__geometry"))
            .annotate(distance=Distance("map__zones__geometry", coords))
            .order_by("distance")
            .select_related("map")
        )
        return perimeters

    def get_zones(self):
        """For debug purpose only.

        Return the Zone objects containing the queried coordinates.
        """
        zones = (
            Zone.objects.filter(geometry__dwithin=(self.catalog["coords"], D(m=0)))
            .select_related("map")
            .prefetch_related("map__perimeters")
            .filter(map__perimeters__isnull=False)
            .distinct()
        )
        return zones

    def is_evaluation_available(self):
        """Moulinette evaluations are only available on some departments.

        When a department is available, we fill it's contact data.
        """
        department = self.catalog["department"]
        contact_info = getattr(department, "contact_md", None)
        return bool(contact_info)

    def has_missing_data(self):
        """Make sure all the data required to compute the result is provided."""

        form_errors = []
        for regulation in self.regulations:
            for criterion in regulation.criterions:
                form = criterion.get_form()
                if form:
                    form_errors.append(not form.is_valid())

        return any(form_errors)

    def cleaned_additional_data(self):
        """Return combined additional data from custom criterion forms."""

        data = {}
        for regulation in self.regulations:
            for criterion in regulation.criterions:
                form = criterion.get_form()
                if form and form.is_valid():
                    data.update(form.cleaned_data)

        return data

    def __getattr__(self, attr):
        """Returs the corresponding regulation.

        Allows to do something like this:
        moulinette.loi_sur_leau to fetch the correct regulation.
        """
        return self.get_regulation(attr)

    def get_regulation(self, regulation_slug):
        """Return the regulation with the given slug."""

        def select_regulation(regulation):
            return regulation.slug == regulation_slug

        regul = next(filter(select_regulation, self.regulations), None)
        return regul

    def result(self):
        """Export all results as a dict."""

        result = {}
        for regulation in self.regulations:
            result[regulation.slug] = {
                "result": regulation.result,
                "criterions": {},
            }
            for criterion in regulation.criterions:
                result[regulation.slug]["criterions"][criterion.slug] = criterion.result

        return result

    def additional_form_classes(self):
        """Return the list of forms for additional questions.

        Some criterions need more data to return an answer. Here, we gather all
        the forms to gather this data.
        """

        forms = []

        for regulation in self.regulations:
            for criterion in regulation.criterions:
                if hasattr(criterion, "form_class"):
                    forms.append(criterion.form_class)

        return forms
