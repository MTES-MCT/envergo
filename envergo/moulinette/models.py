import logging

from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance as D
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Case, F, Prefetch, When
from django.db.models.functions import Cast
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from phonenumber_field.modelfields import PhoneNumberField

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import Department, Zone
from envergo.moulinette.fields import CriterionEvaluatorChoiceField
from envergo.moulinette.regulations import CriterionEvaluator, Map, MapPolygon

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

REGULATIONS = Choices(
    ("loi_sur_leau", "Loi sur l'eau"),
    ("natura2000", "Natura 2000"),
    ("eval_env", "Évaluation environnementale"),
    ("sage", "Règlement de SAGE"),
)


# This is to use in model fields `default` attribute
def all_regulations():
    return list(dict(REGULATIONS._doubles).keys())


class Regulation(models.Model):
    """A single regulation (e.g Loi sur l'eau)."""

    regulation = models.CharField(_("Regulation"), max_length=64, choices=REGULATIONS)
    weight = models.PositiveIntegerField(_("Order"), default=1)

    has_perimeters = models.BooleanField(
        _("Has perimeters"),
        default=False,
        help_text=_("Is this regulation linked to local perimetres?"),
    )
    show_map = models.BooleanField(
        _("Show perimeter map"),
        help_text=_("The perimeter's map will be displayed, if it exists"),
        default=False,
    )
    polygon_color = models.CharField(_("Polygon color"), max_length=7, default="blue")

    class Meta:
        verbose_name = _("Regulation")
        verbose_name_plural = _("Regulations")

    def __str__(self):
        return self.get_regulation_display()

    def __getattr__(self, attr):
        """Returns the corresponding criterion.

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
    def slug(self):
        return self.regulation

    @property
    def title(self):
        return self.get_regulation_display()

    def is_activated(self):
        """Is the regulation activated in the moulinette config?"""

        if not self.moulinette.has_config():
            return False

        config = self.moulinette.config
        regulations_available = config.regulations_available
        activated = self.regulation in regulations_available
        return activated

    def show_criteria(self):
        """Should the criteria be displayed?"""

        if any(
            (
                not self.is_activated(),
                self.has_perimeters and not self.perimeter,
                self.has_perimeters and not self.perimeter.is_activated,
            )
        ):
            return False

        return True

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

        # We start by handling edge cases:
        # - when the regulation is not activated for the department
        # - when the perimeter is not activated
        # - when no perimeter is found
        if not self.is_activated():
            return RESULTS.non_active

        if self.has_perimeters:
            perimeter = self.perimeter
            if perimeter and not perimeter.is_activated:
                return RESULTS.non_disponible
            if not perimeter:
                return RESULTS.non_concerne

        # From this point, we made sure every data (regulation, perimeter) is existing
        # and activated

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

        # If there is no criterion at all, we have to set a default value
        if result is None:
            if self.has_perimeters:
                result = RESULTS.non_soumis
            else:
                result = RESULTS.non_disponible

        return result

    def required_actions(self, stake=None):
        """Return the list of required actions for the given stake."""

        if stake:
            actions = [
                c.required_action
                for c in self.criteria.all()
                if c.required_action
                and c.result == "action_requise"
                and c.required_action_stake == stake
            ]
        else:
            actions = [
                c.required_action
                for c in self.criteria.all()
                if c.required_action and c.result == "action_requise"
            ]
        return actions

    def required_actions_soumis(self):
        return self.required_actions(STAKES.soumis)

    def required_actions_interdit(self):
        return self.required_actions(STAKES.interdit)

    # FIXME: all the impacts of the matched criteria will be displayed, even
    # when said criteria have a "non soumis" result.
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

    @cached_property
    def perimeter(self):
        """Return the administrative perimeter the project is in.

        The perimeter is an administrative zone. In a perfect world, for a single
        regulation, perimeters are non-overlapping, meaning there is a single
        perimeter for a single location.

        French administration being what it is, this is not always the case.

        Hence, if we are matching several perimeters, we have no way to tell which
        one is the correct one. So we just return the first one.
        """
        return self.perimeters.first()

    def display_perimeter(self):
        """Should / can a perimeter be displayed?"""
        return self.is_activated() and self.perimeter

    @property
    def map(self):
        """Returns a map to be displayed for the regulation.

        Returns a `envergo.moulinette.regulations.Map` object or None.
        This map object will be serialized to Json and passed to a Leaflet
        configuration script.
        """
        perimeter = self.perimeter
        if perimeter:
            polygon = MapPolygon([perimeter], self.polygon_color, perimeter.map_legend)
            map = Map(
                center=self.moulinette.catalog["coords"],
                entries=[polygon],
                truncate=False,
                zoom=None,
                ratio="2x1",
                fixed=False,
            )
            return map

        return None

    def display_map(self):
        """Should / can a perimeter map be displayed?"""
        return all((self.is_activated(), self.show_map, self.map))


class Criterion(models.Model):
    """A single criteria for a regulation (e.g. Loi sur l'eau > Zone humide)."""

    backend_title = models.CharField(
        _("Admin title"),
        help_text=_("For backend usage only"),
        max_length=256,
    )
    title = models.CharField(
        _("Title"), help_text=_("For frontend usage"), max_length=256
    )
    slug = models.SlugField(_("Slug"), max_length=256)
    subtitle = models.CharField(_("Subtitle"), max_length=256, blank=True)
    header = models.CharField(_("Header"), max_length=4096, blank=True)
    regulation = models.ForeignKey(
        "moulinette.Regulation",
        verbose_name=_("Regulation"),
        on_delete=models.PROTECT,
        related_name="criteria",
    )
    activation_map = models.ForeignKey(
        "geodata.Map",
        verbose_name=_("Activation map"),
        on_delete=models.PROTECT,
        related_name="criteria",
    )
    activation_distance = models.PositiveIntegerField(
        _("Activation distance"), default=0
    )
    evaluator = CriterionEvaluatorChoiceField(_("Evaluator"))
    weight = models.PositiveIntegerField(_("Order"), default=1)
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

    @property
    def unique_slug(self):
        return f"{self.regulation.slug}__{self.slug}"

    def evaluate(self, moulinette, distance):
        self.moulinette = moulinette
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
    """A perimeter is an administrative zone.

    Examples of perimeters:
     - Sage GMRE
     - Marais de Vilaine

    Perimeters are related to regulations (e.g Natura 2000 Marais de Vilaine).

    """

    backend_name = models.CharField(
        _("Backend name"), help_text=_("For admin usage only"), max_length=256
    )
    name = models.CharField(_("Name"), max_length=256)
    long_name = models.CharField(
        _("Long name"),
        max_length=256,
        blank=True,
        help_text=_("Displayed below the regulation title"),
    )
    is_activated = models.BooleanField(
        _("Is activated"),
        help_text=_("Check if all criteria have been set"),
        default=False,
    )
    regulation = models.ForeignKey(
        "moulinette.Regulation",
        verbose_name=_("Regulation"),
        on_delete=models.PROTECT,
        related_name="perimeters",
    )
    activation_map = models.ForeignKey(
        "geodata.Map",
        verbose_name=_("Map"),
        related_name="perimeters",
        on_delete=models.PROTECT,
    )
    activation_distance = models.PositiveIntegerField(
        _("Activation distance"), default=0
    )
    url = models.URLField(_("Url"), blank=True)
    contact_name = models.CharField(_("Contact name"), max_length=256, blank=True)
    contact_url = models.URLField(_("Contact url"), blank=True)
    contact_phone = PhoneNumberField(_("Contact phone"), blank=True)
    contact_email = models.EmailField(_("Contact email"), blank=True)

    map_legend = models.CharField(_("Map legend"), max_length=256, blank=True)
    rules_url = models.URLField(_("Rules url"))

    class Meta:
        verbose_name = _("Perimeter")
        verbose_name_plural = _("Perimeters")

    def __str__(self):
        return self.name

    @property
    def contact(self):
        """Format an address string."""
        lines = [f"<strong>{self.contact_name or self.long_name or self.name}</strong>"]
        if self.contact_phone:
            lines.append(
                f'Téléphone : <a href="tel:{self.contact_phone}">{self.contact_phone.as_national}</a>'
            )
        if self.contact_url:
            lines.append(
                f'Site web : <a href="{self.contact_url}" target="_blank" rel="noopener">{self.contact_url}</a>'
            )
        if self.contact_email:
            lines.append(
                f'Email : <a href="mailto:{self.contact_email}">{self.contact_email}</a>'
            )
        contact = f"""
        <div class="fr-highlight fr-mb-2w fr-ml-0 fr-mt-1w">
            <address>
                {"<br/>".join(lines)}
            </address>
            </div>
        """
        return mark_safe(contact)


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
    regulations_available = ArrayField(
        base_field=models.CharField(max_length=64, choices=REGULATIONS),
        blank=True,
        default=list,
    )
    ddtm_contact_email = models.EmailField(_("DDT(M) contact email"), blank=True)
    lse_contact_ddtm = models.TextField("LSE > Contact DDTM")
    lse_free_mention = models.TextField(
        "LSE > Mention libre « autres rubriques »", blank=True
    )
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
            self.config = self.catalog["config"] = self.department.moulinette_config

        self.perimeters = self.get_perimeters()
        self.criteria = self.get_criteria()
        self.regulations = self.get_regulations()
        self.evaluate()

        log_data = {
            "raw_data": self.raw_data,
            "result": self.result_data(),
        }
        logger.info(log_data)

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

    def get_criteria(self):
        coords = self.catalog["coords"]

        criteria = (
            Criterion.objects.filter(
                activation_map__zones__geometry__dwithin=(
                    coords,
                    F("activation_distance"),
                )
            )
            .annotate(
                geometry=Case(
                    When(
                        activation_map__geometry__isnull=False,
                        then=F("activation_map__geometry"),
                    ),
                    default=F("activation_map__zones__geometry"),
                )
            )
            .annotate(distance=Distance("activation_map__zones__geometry", coords))
            .order_by("weight")
            .distinct("weight", "id")
            .select_related("activation_map")
            .defer("activation_map__geometry")
        )
        return criteria

    def get_perimeters(self):
        coords = self.catalog["coords"]

        perimeters = (
            Perimeter.objects.filter(
                activation_map__zones__geometry__dwithin=(
                    coords,
                    F("activation_distance"),
                )
            )
            .annotate(
                geometry=Case(
                    When(
                        activation_map__geometry__isnull=False,
                        then=F("activation_map__geometry"),
                    ),
                    default=F("activation_map__zones__geometry"),
                )
            )
            .annotate(distance=Distance("activation_map__zones__geometry", coords))
            .order_by("id")
            .distinct("id")
            .select_related("activation_map")
            .defer("activation_map__geometry")
        )

        return perimeters

    def get_regulations(self):
        """Find the activated regulations and their criteria."""

        regulations = (
            Regulation.objects.all()
            .order_by("weight")
            .prefetch_related(Prefetch("criteria", queryset=self.criteria))
            .prefetch_related(Prefetch("perimeters", queryset=self.perimeters))
        )
        return regulations

    def get_zones(self, coords, radius=200):
        """Return the Zone objects containing the queried coordinates."""

        zones = (
            Zone.objects.filter(geometry__dwithin=(coords, D(m=radius)))
            .annotate(distance=Distance("geometry", coords))
            .annotate(geom=Cast("geometry", MultiPolygonField()))
            .select_related("map")
            .defer("map__geometry")
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

    def result_data(self):
        """Export all results data as a dict."""

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
            summary["result"] = self.result_data()

        return summary

    @property
    def result(self):
        """Compute global result from individual regulation results."""

        results = [regulation.result for regulation in self.regulations]

        # TODO Handle other statuses non_concerne, non_disponible, a_verifier
        rules = [
            ((RESULTS.interdit,), RESULTS.interdit),
            (
                (RESULTS.soumis, RESULTS.systematique, RESULTS.cas_par_cas),
                RESULTS.soumis,
            ),
            ((RESULTS.action_requise,), RESULTS.action_requise),
            ((RESULTS.non_soumis), RESULTS.non_soumis),
        ]

        result = None
        for rule_statuses, rule_result in rules:
            if any(rule_status in results for rule_status in rule_statuses):
                result = rule_result
                break

        result = result or RESULTS.non_soumis

        return result

    def all_required_actions(self):
        for regulation in self.regulations:
            for required_action in regulation.required_actions():
                yield required_action

    def all_required_actions_soumis(self):
        for regulation in self.regulations:
            for required_action in regulation.required_actions_soumis():
                yield required_action

    def all_required_actions_interdit(self):
        for regulation in self.regulations:
            for required_action in regulation.required_actions_interdit():
                yield required_action


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
            for criterion in CriterionEvaluator.__subclasses__()
            if self.catalog[criterion.slug]
        ]
        return criteria

    def get_department(self):
        return self.catalog["department"]
