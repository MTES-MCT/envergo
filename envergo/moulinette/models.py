from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance as D
from django.db import models
from django.db.models import Case, F, When
from django.db.models.functions import Cast
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Department, Zone
from envergo.moulinette.fields import CriterionChoiceField
from envergo.moulinette.regulations import MoulinetteCriterion
from envergo.moulinette.regulations.evalenv import EvalEnvironnementale
from envergo.moulinette.regulations.loisurleau import LoiSurLEau
from envergo.moulinette.regulations.natura2000 import Natura2000
from envergo.moulinette.regulations.sage import Sage
from envergo.utils.markdown import markdown_to_html

# WGS84, geodetic coordinates, units in degrees
# Good for storing data and working wordwide
EPSG_WGS84 = 4326

# Projected coordinates
# Used for displaying tiles in web map systems (OSM, GoogleMaps)
# Good for working in meters
EPSG_MERCATOR = 3857


def fetch_zones_around(coords, radius, zone_type, data_type="certain"):
    """Helper method to fetch Zones around a given point."""

    qs = (
        Zone.objects.filter(map__map_type=zone_type)
        .filter(geometry__dwithin=(coords, D(m=radius)))
        .filter(map__data_type=data_type)
    )
    return qs


# Those dummy methods are useful for unit testing
def fetch_wetlands_around_25m(coords):
    return fetch_zones_around(coords, 25, "zone_humide")


def fetch_wetlands_around_100m(coords):
    return fetch_zones_around(coords, 100, "zone_humide")


def fetch_potential_wetlands(coords):
    qs = (
        Zone.objects.filter(map__map_type="zone_humide")
        .filter(map__data_type="uncertain")
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


class MoulinetteConfig(models.Model):
    """Some moulinette content depends on the department."""

    department = models.OneToOneField(
        "geodata.Department",
        verbose_name=_("Department"),
        on_delete=models.PROTECT,
        related_name="moulinette_config",
    )
    is_activated = models.BooleanField(
        _("Is activated"),
        help_text=_("Is the moulinette available for this department?"),
        default=False,
    )
    ddtm_contact_email = models.EmailField(_("DDT(M) contact email"), blank=True)
    lse_contact_ddtm = models.TextField("LSE > Contact DDTM")
    n2000_contact_ddtm_info = models.TextField("N2000 > Contact DDTM info")
    n2000_contact_ddtm_instruction = models.TextField(
        "N2000 > Contact DDTM instruction"
    )
    n2000_procedure_ein = models.TextField("N2000 > Procédure EIN")
    n2000_lotissement_proximite = models.TextField(
        "N2000 > Précision proximité immédiate",
        blank=True,
    )
    evalenv_procedure_casparcas = models.TextField("EvalEnv > Procédure cas par cas")
    criteria_values = models.JSONField(
        "Valeurs des critères", default=dict, null=True, blank=True
    )

    class Meta:
        verbose_name = _("Moulinette config")
        verbose_name_plural = _("Moulinette configs")

    def __str__(self):
        return self.department.get_department_display()


class MoulinetteCatalog(dict):
    """Custom class responsible for fetching data used in regulation evaluations.

    The catalog is passed to Regulation and Criterion objects, and those objects
    can contribute data to the dictionary.

    But some data is used in several criterions, so it must be fetched beforehand.
    """

    def __missing__(self, key):
        """If the data is not in the dict, use a method to fetch it."""

        if not hasattr(self, key):
            raise KeyError(f"Donnée manquante : {key}")

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
        self.department = self.get_department()
        if hasattr(self.department, "moulinette_config"):
            self.catalog["config"] = self.department.moulinette_config

        self.perimeters = self.get_perimeters()
        self.criterions_classes = self.get_criterions()

        # This is a clear case of circular references, since the Moulinette
        # holds references to the regulations it's computing, but regulations and
        # criterions holds a reference to the Moulinette.
        # That is because the Reality™ is messy and sometimes criterions require
        # access to other pieces of data from the moulinette.
        # For example, to compute the "Natura2000" result, there is a criterion
        # that is just the result of the "Loi sur l'eau" regulation.
        self.regulations = [
            LoiSurLEau(self),
            Sage(self),
            Natura2000(self),
            EvalEnvironnementale(self),
        ]

        self.catalog.update(self.cleaned_additional_data())

    def get_department(self):
        lng_lat = self.catalog["lng_lat"]
        department = Department.objects.filter(geometry__contains=lng_lat).first()
        return department

    def get_catalog_data(self):
        """Fetch / compute data required for further computations."""

        catalog = {}

        lng = self.catalog["lng"]
        lat = self.catalog["lat"]
        catalog["lng_lat"] = Point(float(lng), float(lat), srid=EPSG_WGS84)
        catalog["coords"] = catalog["lng_lat"].transform(EPSG_MERCATOR, clone=True)
        catalog["circle_12"] = catalog["coords"].buffer(12)
        catalog["circle_25"] = catalog["coords"].buffer(25)
        catalog["circle_100"] = catalog["coords"].buffer(100)

        fetching_radius = int(self.raw_data.get("radius", "200"))
        zones = self.get_zones(catalog["coords"], fetching_radius)
        catalog["all_zones"] = zones

        def wetlands_filter(zone):
            return all(
                (
                    zone.map.map_type == "zone_humide",
                    zone.map.data_type == "certain",
                )
            )

        catalog["wetlands"] = list(filter(wetlands_filter, zones))

        def potential_wetlands_filter(zone):
            return all(
                (
                    zone.map.map_type == "zone_humide",
                    zone.map.data_type == "uncertain",
                )
            )

        catalog["potential_wetlands"] = list(filter(potential_wetlands_filter, zones))

        def forbidden_wetlands_filter(zone):
            return all(
                (
                    zone.map.map_type == "zone_humide",
                    zone.map.data_type == "forbidden",
                )
            )

        catalog["forbidden_wetlands"] = list(filter(forbidden_wetlands_filter, zones))

        def flood_zones_filter(zone):
            return all(
                (
                    zone.map.map_type == "zone_inondable",
                    zone.map.data_type == "certain",
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
            .annotate(
                geometry=Case(
                    When(map__geometry__isnull=False, then=F("map__geometry")),
                    default=F("map__zones__geometry"),
                )
            )
            .annotate(distance=Distance("map__zones__geometry", coords))
            .order_by("distance", "map__name")
            .select_related("map", "contact")
        )
        return perimeters

    def get_criterions(self):
        criterions = []
        for perimeter in self.perimeters:
            criterion = perimeter.criterion
            if hasattr(perimeter, "contact"):
                criterion.contact = perimeter.contact
            criterions.append(criterion)
        return set(criterions)

    def get_zones(self, coords, radius=200):
        """Return the Zone objects containing the queried coordinates."""

        zones = (
            Zone.objects.filter(geometry__dwithin=(coords, D(m=radius)))
            .annotate(distance=Distance("geometry", coords))
            .annotate(geom=Cast("geometry", MultiPolygonField()))
            .select_related("map")
            .order_by("distance", "map__name")
        )
        return zones

    def has_config(self):
        config = getattr(self.department, "moulinette_config", None)
        return bool(config)

    def is_evaluation_available(self):
        """Moulinette evaluations are only available on some departments.

        When a department is available, we fill it's contact data.
        """
        config = getattr(self.department, "moulinette_config", None)
        return config and config.is_activated

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

    def summary(self):
        """Build a data summary, for analytics purpose."""

        department = self.department
        department_code = department.department if department else ""

        summary = {
            "lat": f'{self.catalog["lat"]:.5f}',
            "lng": f'{self.catalog["lng"]:.5f}',
            "existing_surface": self.catalog["existing_surface"],
            "created_surface": self.catalog["created_surface"],
            "final_surface": self.catalog["final_surface"],
            "department": department_code,
            "is_eval_available": self.is_evaluation_available(),
        }
        summary.update(self.cleaned_additional_data())

        if self.is_evaluation_available():
            summary["result"] = self.result()

        return summary


class FakeMoulinette(Moulinette):
    """This is a custom Moulinette subclass used for debugging purpose.

    A single moulinette simulation tests many criteria, each criterion can
    have a different result code, resulting in specific regulation results.

    Every single criterion unique result is displayed with a dedicated template.
    Moreover, some data may change depending on the department the simulation
    is ran.

    For this reason, it can be very cumbersome for the EnvErgo team members
    to review and test each and every possibility.

    That's why a custom page was created, allowing to manually select the exact
    Moulinette result combination we want to display.

    This `FakeMoulinette` is a utility class that must be initialized with a
    dict of data where each key is a single criterion slug and the associated
    value is the `result_code` we want the criterion to return.
    """

    def __init__(self, fake_data):
        dummy_data = {
            "lat": 1.7,
            "lng": 47,
            "created_surface": 50,
            "existing_surface": 50,
        }
        dummy_data.update(fake_data)
        super().__init__(dummy_data, dummy_data)

        # Override the `result_code` for each criterion
        # Since `result_code` is a property, we cannot directly monkeypatch the
        # property.
        # Hence, we have to override the value at the class level
        for regulation in self.regulations:
            for criterion in regulation.criterions:
                setattr(
                    criterion.__class__, "result_code", self.catalog[criterion.slug]
                )

    def get_criterions(self):
        criteria = [
            criterion
            for criterion in MoulinetteCriterion.__subclasses__()
            if self.catalog[criterion.slug]
        ]
        return criteria

    def get_department(self):
        return self.catalog["department"]


class Contact(models.Model):
    """Contact data for a perimeter."""

    perimeter = models.OneToOneField(
        Perimeter,
        verbose_name=_("Perimeter"),
        on_delete=models.PROTECT,
        related_name="contact",
    )
    name = models.CharField(_("Name"), max_length=256)
    url = models.URLField(_("URL"), blank=True)
    address_md = models.TextField(_("Address"))
    address_html = models.TextField(_("Address HTML"), blank=True)

    class Meta:
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.address_html = markdown_to_html(self.address_md)
        super().save(*args, **kwargs)
