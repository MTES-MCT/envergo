import logging

from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance as D
from django.db import models
from django.db.models import Case, F, Prefetch, When
from django.db.models.functions import Cast
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import Department, Zone
from envergo.moulinette.fields import (
    CriterionChoiceField,
    CriterionEvaluatorChoiceField,
)
from envergo.moulinette.regulations import Map, MapPolygon, MoulinetteCriterion
from envergo.utils.markdown import markdown_to_html

# WGS84, geodetic coordinates, units in degrees
# Good for storing data and working wordwide
EPSG_WGS84 = 4326

# Projected coordinates
# Used for displaying tiles in web map systems (OSM, GoogleMaps)
# Good for working in meters
EPSG_MERCATOR = 3857


logger = logging.getLogger(__name__)


# A list of required action stakes.
# For example, a user might learn that an action is required, to check if the
# project is subject to the Water Law. Or if the project is forbidden.
STAKES = Choices(
    ("soumis", "Soumis"),
    ("interdit", "Interdit"),
)


class Regulation(models.Model):
    """A single regulation (e.g Loi sur l'eau)."""

    title = models.CharField(_("Title"), max_length=256)
    slug = models.SlugField(_("Slug"), max_length=256)
    perimeter = models.ForeignKey(
        "geodata.Map",
        verbose_name=_("Perimeter"),
        on_delete=models.PROTECT,
        related_name="regulations",
    )
    activation_distance = models.PositiveIntegerField(
        _("Activation distance"), default=0
    )
    weight = models.PositiveIntegerField(_("Weight"), default=1)

    show_map = models.BooleanField(_("Show map"), default=False)
    map_caption = models.TextField(_("Map caption"), blank=True)
    polygon_color = models.CharField(_("Polygon color"), max_length=7, default="blue")

    class Meta:
        verbose_name = _("Regulation")
        verbose_name_plural = _("Regulations")

    def __str__(self):
        return self.title

    def __getattr__(self, attr):
        """Returns the corresponding regulation.

        Allows to do something like this:
        moulinette.loi_sur_leau.zone_humide to fetch the correct regulation.
        """

        def select_criterion(criterion):
            return criterion.slug == attr

        # If we just call `self.criteria.all(), we will trigger a recursive call
        # to __getattr__.
        # To avoid this, we get that data from the prefetched cache instead
        if (
            "_prefetched_objects_cache" in self.__dict__
            and "criteria" in self.__dict__["_prefetched_objects_cache"]
        ):
            criteria = self.__dict__["_prefetched_objects_cache"]["criteria"]
            if criteria:
                criterion = next(filter(select_criterion, criteria), None)
                if criterion:
                    return criterion
        val = getattr(super(), attr)
        return val

    def get_criterion(self, criterion_slug):
        """Return the criterion with the given slug."""

        def select_criterion(criterion):
            return criterion.slug == criterion_slug

        criterion = next(filter(select_criterion, self.criteria.all()), None)
        if criterion is None:
            logger.warning(f"Criterion {criterion_slug} not found.")
        return criterion

    def evaluate(self, moulinette):
        """Evaluate the regulation and all its criterions.

        Note : the `distance` field is not a member of the Criterion model,
        it is added with an annotation in the `get_regulations` method.
        """
        self.moulinette = moulinette
        for criterion in self.criteria.all():
            criterion.evaluate(moulinette, criterion.distance)

    @property
    def result(self):
        """Compute global result from individual criterions.

        When we perform an evaluation, a single regulation has many criteria.
        Criteria can have different results, but we display a single value for
        the regulation result.

        We can reduce different criteria results into a single regulation
        result because results have different priorities.

        For example, if a single criterion has the "interdit" result, the
        regulation result will be "interdit" too, no matter what the other
        criteria results are. Then it will be "soumis", etc.

        Different regulations have different set of possible result values, e.g
        only the Évaluation environnementale regulation has the "cas par cas" or
        "systematique" results, but the cascade still works.
        """

        cascade = [
            RESULTS.interdit,
            RESULTS.systematique,
            RESULTS.cas_par_cas,
            RESULTS.soumis,
            RESULTS.action_requise,
            RESULTS.a_verifier,
            RESULTS.non_soumis,
            RESULTS.non_concerne,
            RESULTS.non_disponible,
        ]
        results = [criterion.result for criterion in self.criteria.all()]
        result = None
        for status in cascade:
            if status in results:
                result = status
                break

        # Special case for the Natura2000 regulation, the criterion and
        # regulation statuses are different
        if result == RESULTS.a_verifier:
            result = RESULTS.iota_a_verifier

        # If there is no criterion at all, set a default result of "non disponible"
        if result is None:
            result = RESULTS.non_disponible

        return result

    def required_actions(self, stake):
        """Return the list of required actions for the given stake."""

        actions = [
            c.required_action
            for c in self.criteria.all()
            if c.required_action
            and c.result == "action_requise"
            and c.required_action_stake == stake
        ]
        return actions

    def required_actions_soumis(self):
        return self.required_actions(STAKES.soumis)

    def required_actions_interdit(self):
        return self.required_actions(STAKES.interdit)

    def project_impacts(self):
        impacts = [c.project_impact for c in self.criteria.all() if c.project_impact]
        return impacts

    def discussion_contacts(self):
        contacts = [
            c.discussion_contact for c in self.criteria.all() if c.discussion_contact
        ]
        return contacts

    def iota_only(self):
        """Is the IOTA criterion the only valid criterion.

        There is an edge case for the Natura2000 regulation.
        Projects can be subject to Natura2000 only
        because they are subject to IOTA, even though they are outsite
        Natura 2000 zones.
        """
        criteria_slugs = [c.slug for c in self.criteria.all()]
        return criteria_slugs == ["iota"]

    @property
    def map(self):
        """Returns a map to be displayed for the regulation.

        Returns a `envergo.moulinette.regulations.Map` object or None.
        This map object will be serialized to Json and passed to a Leaflet
        configuration script.
        """
        if not self.show_map:
            return None

        polygon = MapPolygon([self.perimeter], self.polygon_color, self.title)
        map = Map(
            center=self.moulinette.catalog["coords"],
            entries=[polygon],
            caption=self.map_caption,
            truncate=False,
            zoom=None,
        )
        return map


class Criterion(models.Model):
    """A single criteria for a regulation (e.g. Loi sur l'eau > Zone humide)."""

    title = models.CharField(_("Title"), max_length=256)
    slug = models.SlugField(_("Slug"), max_length=256)
    subtitle = models.CharField(_("Subtitle"), max_length=256, blank=True)
    header = models.CharField(_("Header"), max_length=4096, blank=True)
    evaluator = CriterionEvaluatorChoiceField(_("Evaluator"))
    perimeter = models.ForeignKey(
        "geodata.Map",
        verbose_name=_("Perimeter"),
        on_delete=models.PROTECT,
        related_name="criteria",
    )
    activation_distance = models.PositiveIntegerField(
        _("Activation distance"), default=0
    )
    regulation = models.ForeignKey(
        "moulinette.Regulation",
        verbose_name=_("Regulation"),
        on_delete=models.PROTECT,
        related_name="criteria",
    )
    weight = models.PositiveIntegerField(_("Weight"), default=1)
    required_action = models.CharField(
        _("Required action"),
        help_text="Le porteur doit s'assurer que son projet…",
        max_length=256,
        blank=True,
    )
    required_action_stake = models.CharField(
        _("Required action stake"), choices=STAKES, max_length=32, blank=True
    )
    project_impact = models.CharField(
        _("Project impact"),
        help_text="Au vu des informations saisies, le projet…",
        max_length=256,
        blank=True,
    )
    discussion_contact = models.TextField(
        _("Discussion contact (html)"),
        help_text="Le porteur de projet peut se rapprocher…",
        blank=True,
    )

    class Meta:
        verbose_name = _("Criterion")
        verbose_name_plural = _("Criteria")

    def __str__(self):
        return self.title

    def evaluate(self, moulinette, distance):
        self._evaluator = self.evaluator(moulinette, distance)
        self._evaluator.evaluate()

    @property
    def result_code(self):
        """Return the criterion result code."""
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Criterion must be evaluated before accessing the result code."
            )

        return self._evaluator.result_code

    @property
    def result(self):
        """Return the criterion result."""
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Criterion must be evaluated before accessing the result."
            )

        return self._evaluator.result

    @property
    def map(self):
        """Returns a map to be displayed for a single criterion.

        Returns a `envergo.moulinette.regulations.Map` object or None.
        This map object will be serialized to Json and passed to a Leaflet
        configuration script.
        """
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Criterion must be evaluated before accessing the result code."
            )

        try:
            map = self._evaluator.get_map()
        except:  # noqa
            map = None
        return map

    def get_form_class(self):
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Criterion must be evaluated before accessing the form class."
            )

        return self._evaluator.get_form_class()

    def get_form(self):
        if not hasattr(self, "_evaluator"):
            raise RuntimeError("Criterion must be evaluated before accessing the form.")

        return self._evaluator.get_form()


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

        self.regulations = self.get_regulations()
        self.evaluate()

    def evaluate(self):
        for regulation in self.regulations:
            regulation.evaluate(self)

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

    def get_regulations(self):
        """Find the activated regulations and their criteria."""

        coords = self.catalog["coords"]

        criteria = (
            Criterion.objects.filter(
                perimeter__zones__geometry__dwithin=(coords, F("activation_distance"))
            )
            .annotate(
                geometry=Case(
                    When(
                        perimeter__geometry__isnull=False, then=F("perimeter__geometry")
                    ),
                    default=F("perimeter__zones__geometry"),
                )
            )
            .annotate(distance=Distance("perimeter__zones__geometry", coords))
            .order_by("weight")
            .select_related("perimeter")
        )

        regulations = (
            Regulation.objects.filter(
                perimeter__zones__geometry__dwithin=(coords, F("activation_distance"))
            )
            .annotate(
                geometry=Case(
                    When(
                        perimeter__geometry__isnull=False, then=F("perimeter__geometry")
                    ),
                    default=F("perimeter__zones__geometry"),
                )
            )
            .annotate(distance=Distance("perimeter__zones__geometry", coords))
            .order_by("weight")
            .select_related("perimeter")
            .prefetch_related(Prefetch("criteria", queryset=criteria))
        )
        return regulations

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
            for criterion in regulation.criteria.all():
                form = criterion.get_form()
                if form:
                    form_errors.append(not form.is_valid())

        return any(form_errors)

    def cleaned_additional_data(self):
        """Return combined additional data from custom criterion forms."""

        data = {}
        for regulation in self.regulations:
            for criterion in regulation.criteria.all():
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
        if regul is None:
            logger.warning(f"Regulation {regulation_slug} not found.")
        return regul

    def result(self):
        """Export all results as a dict."""

        result = {}
        for regulation in self.regulations:
            result[regulation.slug] = {
                "result": regulation.result,
                "criterions": {},
            }
            for criterion in regulation.criteria.all():
                result[regulation.slug]["criterions"][criterion.slug] = criterion.result

        return result

    def additional_form_classes(self):
        """Return the list of forms for additional questions.

        Some criterions need more data to return an answer. Here, we gather all
        the forms to gather this data.
        """

        forms = []

        for regulation in self.regulations:
            for criterion in regulation.criteria.all():
                form_class = criterion.get_form_class()
                if form_class:
                    forms.append(form_class)

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
    regulation_url = models.URLField(_("Regulation URL"), blank=True)
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
