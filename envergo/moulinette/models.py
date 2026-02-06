import logging
from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict
from datetime import date, datetime
from enum import IntEnum
from itertools import groupby
from operator import attrgetter
from typing import Literal

from dateutil import parser
from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.functions import Centroid, Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance as D
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField, DateRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import (
    CheckConstraint,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
)
from django.db.models import Value
from django.db.models import Value as V
from django.db.models.functions import Cast, Coalesce, Concat
from django.forms import BoundField, Form
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from phonenumber_field.modelfields import PhoneNumberField
from django.db.backends.postgresql.psycopg_any import DateRange

from envergo.evaluations.models import (
    RESULT_CASCADE,
    RESULTS,
    TAG_STYLES_BY_RESULT,
    USER_TYPES,
    TagStyleEnum,
)
from envergo.geodata.models import Department, Zone
from envergo.hedges.forms import HedgeToPlantPropertiesForm, HedgeToRemovePropertiesForm
from envergo.hedges.models import TO_PLANT, TO_REMOVE, HedgeData
from envergo.moulinette.fields import (
    CriterionEvaluatorChoiceField,
    RegulationEvaluatorChoiceField,
    get_subclasses,
)
from envergo.moulinette.forms import (
    DisplayIntegerField,
    MoulinetteFormAmenagement,
    MoulinetteFormHaie,
    TriageFormHaie,
)
from envergo.moulinette.regulations import (
    HaieRegulationEvaluator,
    HedgeDensityMixin,
    MapFactory,
)
from envergo.moulinette.utils import compute_surfaces, list_moulinette_templates
from envergo.utils.tools import insert_before

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

ACTIVATION_MODES = Choices(
    ("department_centroid", "Centroïde du département dans la carte"),
    (
        "hedges_intersection",
        "Intersection de la carte et des haies (à la fois à détruire et à planter)",
    ),
)

REGULATIONS = Choices(
    ("loi_sur_leau", "Loi sur l'eau"),
    ("natura2000", "Natura 2000"),
    ("natura2000_haie", "Natura 2000 Haie"),
    ("eval_env", "Évaluation environnementale"),
    ("sage", "Règlement de SAGE"),
    ("conditionnalite_pac", "Conditionnalité PAC"),
    ("ep", "Espèces protégées"),
    ("alignement_arbres", "Alignements d'arbres (L350-3)"),
    ("urbanisme_haie", "Urbanisme haie"),
    ("reserves_naturelles", "Réserves naturelles"),
    ("code_rural_haie", "Code rural"),
    ("regime_unique_haie", "Régime unique haie"),
    ("sites_proteges_haie", "Sites protégés"),
    ("sites_inscrits_haie", "Sites inscrits"),
    ("sites_classes_haie", "Sites classés"),
)


GLOBAL_RESULT_MATRIX = {
    RESULTS.interdit: RESULTS.interdit,
    RESULTS.systematique: RESULTS.soumis,
    RESULTS.cas_par_cas: RESULTS.soumis,
    RESULTS.soumis_ou_pac: RESULTS.soumis,
    RESULTS.soumis: RESULTS.soumis,
    RESULTS.soumis_declaration: RESULTS.soumis,
    RESULTS.soumis_autorisation: RESULTS.soumis,
    RESULTS.derogation_inventaire: RESULTS.soumis,
    RESULTS.derogation_simplifiee: RESULTS.soumis,
    RESULTS.dispense_sous_condition: RESULTS.soumis,
    RESULTS.action_requise: RESULTS.action_requise,
    RESULTS.a_verifier: RESULTS.action_requise,
    RESULTS.iota_a_verifier: RESULTS.action_requise,
    RESULTS.non_soumis: RESULTS.non_soumis,
    RESULTS.dispense: RESULTS.non_soumis,
    RESULTS.non_concerne: RESULTS.non_soumis,
    RESULTS.non_disponible: RESULTS.non_disponible,
    RESULTS.non_applicable: RESULTS.non_disponible,
    RESULTS.non_active: RESULTS.non_disponible,
}


_missing_results = [key for (key, label) in RESULTS if key not in GLOBAL_RESULT_MATRIX]
if _missing_results:
    raise ValueError(
        f"The following RESULTS are missing in GLOBAL_RESULT_MATRIX: {_missing_results}"
    )


# This is to use in model fields `default` attribute
def all_regulations():
    return list(dict(REGULATIONS._doubles).keys())


class ResultGroupEnum(IntEnum):
    """Depending on their result, the regulation will be impacting more or less the project. This group defines the
    level of impact of the regulation on the project.

    The int value, is used to define the order of the group in the cascade (e.g. for display).
    """

    BlockingRegulations = (
        1  # if there is some regulation in this group, the project cannot go further
    )
    RestrictiveRegulations = 2  # a dossier will be required
    UnsimulatedRegulations = 3  # has an impact but will not be simulated
    OtherRegulations = 4  # these regulations do not impact the project


RESULTS_GROUP_MAPPING = {
    RESULTS.interdit: ResultGroupEnum.BlockingRegulations,
    RESULTS.systematique: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.cas_par_cas: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.soumis: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.soumis_ou_pac: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.soumis_declaration: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.soumis_autorisation: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.derogation_inventaire: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.derogation_simplifiee: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.action_requise: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.a_verifier: ResultGroupEnum.UnsimulatedRegulations,
    RESULTS.iota_a_verifier: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.dispense_sous_condition: ResultGroupEnum.RestrictiveRegulations,
    RESULTS.non_soumis: ResultGroupEnum.OtherRegulations,
    RESULTS.dispense: ResultGroupEnum.OtherRegulations,
    RESULTS.non_concerne: ResultGroupEnum.OtherRegulations,
    RESULTS.non_disponible: ResultGroupEnum.UnsimulatedRegulations,
    RESULTS.non_applicable: ResultGroupEnum.OtherRegulations,
    RESULTS.non_active: ResultGroupEnum.OtherRegulations,
}


def _check_results_groups_matrices():
    _missing_results = set()
    _missing_groups = set()

    for key, value in RESULTS:
        if key not in RESULTS_GROUP_MAPPING:
            _missing_results.add(key)
            continue
        if not isinstance(RESULTS_GROUP_MAPPING[key], ResultGroupEnum):
            _missing_groups.add(RESULTS_GROUP_MAPPING[key])
    if _missing_results:
        raise ValueError(
            f"The following RESULTS are missing in RESULTS_GROUP_KEYS: {_missing_results}"
        )
    if _missing_groups:
        raise ValueError(
            f"The following value is not from ResultGroupEnum: {_missing_groups}"
        )


_check_results_groups_matrices()


ACTIONS_TO_TAKE = Choices(
    (
        "mention_arrete_lse",
        "Mentionner dans l’arrêté le différé de réalisation des travaux",
    ),
    ("depot_pac_lse", "Déposer un porter-à-connaissance auprès de la DDT(M)"),
    ("depot_dossier_lse", "Déposer un dossier Loi sur l'eau"),
    ("etude_zh_lse", "LSE > Réaliser un inventaire zones humides"),
    ("etude_zi_lse", "LSE > Réaliser une étude hydraulique"),
    ("etude_2150", "Réaliser une étude de gestion des eaux pluviales"),
    ("depot_etude_impact", "Déposer un dossier d'évaluation environnementale"),
    ("depot_cas_par_cas", "Déposer une demande d’examen au cas par cas"),
    ("depot_ein", "Réaliser une évaluation des incidences Natura 2000"),
    ("etude_zh_n2000", "Natura 2000 > Réaliser un inventaire zones humides"),
    ("etude_zi_n2000", "Natura 2000 > Réaliser une étude hydraulique"),
    (
        "pc_cas_par_cas",
        "L’arrêté préfectoral portant décision suite à l’examen au cas par cas",
    ),
    ("pc_ein", "L’évaluation des incidences Natura 2000"),
)


def get_map_factory_class_names():
    return [
        (f"{self.__module__}.{self.__name__}", self.human_readable_name())
        for self in get_subclasses(MapFactory)
    ]


class Regulation(models.Model):
    """A single regulation (e.g Loi sur l'eau)."""

    regulation = models.CharField(_("Regulation"), max_length=64, choices=REGULATIONS)

    custom_title = models.CharField(
        "Titre personnalisé (facultatif)",
        help_text="Si non renseigné, le nom de la réglementation sera utilisé.",
        max_length=256,
        blank=True,
    )
    evaluator = RegulationEvaluatorChoiceField(_("Evaluator"))

    weight = models.PositiveIntegerField("Ordre de calcul", default=1)

    display_order = models.PositiveIntegerField("Ordre d'affichage", default=1)

    has_perimeters = models.BooleanField(
        "Réglementation liée aux périmètres ?",
        default=False,
        help_text="Le calcul du résultat dépend de la présence ou non de périmètres,"
        " en plus des résultats des critères",
    )
    show_map = models.BooleanField(
        _("Show perimeter map"),
        help_text=_("The perimeter's map will be displayed, if it exists"),
        default=False,
    )
    polygon_color = models.CharField(_("Polygon color"), max_length=7, default="blue")

    map_factory_name = models.CharField(
        "Type de carte affichée",
        choices=get_map_factory_class_names(),
        max_length=256,
        blank=True,
    )

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

    def get_optional_criteria(self):
        optional_criteria = [
            c
            for c in self.criteria.all()
            if c.is_optional and c.result != "non_disponible"
        ]
        return optional_criteria

    def evaluate(self, moulinette):
        """Evaluate the regulation and all its criterions.

        Note : the `distance` field is not a member of the Criterion model,
        it is added with an annotation in the `get_regulations` method.
        """
        self.moulinette = moulinette
        for criterion in self.criteria.all():
            criterion.evaluate(moulinette, criterion.distance)

        self._evaluator = self.evaluator(moulinette)
        self._evaluator.evaluate(self)

    @property
    def result(self):
        """Return the regulation result."""
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Regulation must be evaluated before accessing the result."
            )

        return self._evaluator.result

    @property
    def procedure_type(self):
        """Return the regulation procedure type (autorisation / déclaration / hors r.u)."""
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Regulation must be evaluated before accessing the proceture type."
            )

        return self._evaluator.procedure_type

    @property
    def slug(self):
        return self.regulation

    @property
    def title(self):
        return self.custom_title or self.get_regulation_display()

    @property
    def subtitle(self):
        subtitle_property = f"{self.regulation}_subtitle"
        sub = getattr(self, subtitle_property, None)
        return sub

    def is_activated(self):
        """Is the regulation activated in the moulinette config?"""

        if not self.moulinette.has_config():
            return False

        config = self.moulinette.config
        regulations_available = config.regulations_available
        activated = self.regulation in regulations_available
        return activated

    def show_criteria(self):
        """Should the criteria be displayed?

        We musn't display criteria if the regulation or associated perimeters are
        not activated yet.
        """

        activated_perimeters = [p for p in self.perimeters.all() if p.is_activated]
        return self.is_activated() and (
            (not self.has_perimeters)
            or (self.has_perimeters and any(activated_perimeters))
        )

    @property
    def results_by_perimeter(self):
        """Compute global result for each perimeter for which this regulation is activated.

        When there is several perimeters, we may want to display some different
        information depending on the result of each single perimeter.
        E.g. if the project is impacting two different SAGE, we may have some
        different required actions for each of them.

        This method is using the same cascading logic as the `result` property,
        to reduce multiple criteria results to a single value.

        The results are sorted based on the result cascade, because we want to
        display first the most restrictive results.
        """
        if not self.has_perimeters:
            return None

        results_by_perimeter = {}

        # Fetch already evaluated criteria
        criteria_list = list(self.criteria.all())
        criteria_list.sort(key=attrgetter("perimeter_id"))
        grouped_criteria = {
            k: list(v) for k, v in groupby(criteria_list, key=attrgetter("perimeter"))
        }

        for perimeter in self.perimeters.all():
            criteria = grouped_criteria.get(perimeter, [])
            results = [criterion.result for criterion in criteria]
            result = None
            for status in RESULT_CASCADE:
                if status in results:
                    result = status
                    break
            # If there is no criterion at all, we have to set a default value
            if result is None:
                if perimeter.is_activated:
                    result = RESULTS.non_soumis
                else:
                    result = RESULTS.non_disponible
            results_by_perimeter[perimeter] = result

        # sort based on the results cascade
        return OrderedDict(
            sorted(
                results_by_perimeter.items(),
                key=lambda item: RESULT_CASCADE.index(item[1]),
            )
        )

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
        return list(set(actions))

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

    def ein_out_of_n2000_site(self):
        """Is the project subject to n2000 even if it is not in a Natura 2000 zone ?

        There is an edge case for the Natura2000 regulation.
        Projects can be subject to Natura2000 only
        because they are subject to IOTA or Evaluation Environnemental, even though they are outside
        Natura 2000 zones.
        """
        criteria_slugs = [c.slug for c in self.criteria.all()]
        return criteria_slugs and all(
            item in ["iota", "eval_env"] for item in criteria_slugs
        )

    def autorisation_urba_needed(self):
        """Is an "autorisation d'urbanisme" needed?

        This is a custom check for the N2000 regulation.
        Such an authorization is required if the answer to the "autorisation d'urbanisme"
        question is anything other than "no".

        Also, the value is "True" by default if the "autorisation_urba" question is
        not present.
        """

        try:
            autor_urba_form = self.get_criterion("autorisation_urba").get_form()
            if (
                autor_urba_form.is_valid()
                and autor_urba_form.cleaned_data["autorisation_urba"] == "none"
            ):
                return False
        except AttributeError:
            pass

        return True

    def display_perimeter(self):
        """Should / can a perimeter be displayed?"""
        return self.is_activated() and bool(self.perimeters.all())

    @property
    def map_factory(self):
        """Instantiate the map factory class from its name"""
        if not self.map_factory_name:
            return None

        return import_string(self.map_factory_name)(self)

    @property
    def map(self):
        """Returns a map to be displayed for the regulation.

        Returns a `envergo.moulinette.regulations.Map` object or None.
        This map object will be serialized to Json and passed to a Leaflet
        configuration script.
        """
        return self.map_factory.create_map() if self.map_factory else None

    def display_map(self):
        """Should / can a perimeter map be displayed?"""
        return self.is_activated() and self.show_map and self.map

    def has_several_perimeters(self):
        return len(self.perimeters.all()) > 1

    @property
    def result_tag_style(self):
        """Return the regulation result tag style."""
        if not self.result:
            return TagStyleEnum.Grey

        return TAG_STYLES_BY_RESULT[self.result]

    @property
    def result_group(self):
        """Get the result group of the regulation, depending on its impact on the project."""
        return RESULTS_GROUP_MAPPING[self.result]

    def has_instructor_result_details_template(self) -> bool:
        """Check if the regulation has a template for instructor result details."""
        return self.has_template("haie/petitions/{}/instructor_result_details.html")

    def has_plantation_condition_details_template(self) -> bool:
        """Check if the regulation has a template for plantation condition details for at least one criterion."""
        return self.has_criterion_template(
            "haie/petitions/{}/{}_plantation_condition_details.html"
        )

    def has_key_elements_template(self) -> bool:
        """Check if the regulation has a template for key elements."""
        return self.has_template("haie/petitions/{}/key_elements.html")

    def has_instruction_guidelines_template(self) -> bool:
        """Check if the regulation has a template for guidelines for instruction."""
        return self.has_template("haie/petitions/{}/instruction_guidelines.html")

    def has_criterion_template(self, template_path) -> bool:
        """Check if the regulation has a template of the given path for at least one criterion."""
        for criterion in self.criteria.all():
            try:
                get_template(template_path.format(self.slug, criterion.slug))
                return True
            except TemplateDoesNotExist:
                pass
        return False

    def has_template(self, template_path) -> bool:
        """Check if the regulation has a template of the given path."""
        try:
            get_template(template_path.format(self.slug))
            return True
        except TemplateDoesNotExist:
            return False

    @property
    def actions_to_take(self) -> set[str]:
        """Get potential actions to take from regulation result."""
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Regulation must be evaluated before accessing actions to take."
            )

        if hasattr(self._evaluator, "actions_to_take"):
            actions_to_take = set(self._evaluator.actions_to_take)
        else:
            actions_to_take = set()

        return actions_to_take

    def get_evaluator(self):
        """Return the evaluator instance."""
        return self._evaluator


class CriterionQuerySet(models.QuerySet):
    """QuerySet for Criterion models with validity date filtering."""

    def valid_at(self, date):
        """Filter criteria valid at the given date."""
        return self.filter(
            Q(validity_range__contains=date) | Q(validity_range__isnull=True)
        )


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
    subtitle = models.CharField(_("Subtitle"), max_length=256, blank=True)
    header = models.CharField(_("Header"), max_length=4096, blank=True)

    validity_range = DateRangeField(
        "Dates de validité",
        blank=True,
        null=True,
    )
    regulation = models.ForeignKey(
        "moulinette.Regulation",
        verbose_name=_("Regulation"),
        on_delete=models.PROTECT,
        related_name="criteria",
    )
    perimeter = models.ForeignKey(
        "moulinette.Perimeter",
        verbose_name=_("Perimeter"),
        on_delete=models.PROTECT,
        related_name="criteria",
        null=True,
        blank=True,
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
    activation_mode = models.CharField(
        "Mode d'activation (GUH uniquement)",
        choices=ACTIVATION_MODES,
        max_length=32,
        blank=True,
    )
    evaluator = CriterionEvaluatorChoiceField(_("Evaluator"))
    evaluator_settings = models.JSONField(
        _("Evaluator settings"), default=dict, blank=True
    )
    is_optional = models.BooleanField(
        _("Is optional"),
        default=False,
        help_text="Ne s'applique que sur activation expresse de l'utilisateur (questions « optionnelles »)",
    )
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

    objects = CriterionQuerySet.as_manager()

    class Meta:
        verbose_name = _("Criterion")
        verbose_name_plural = _("Criteria")
        constraints = [
            models.CheckConstraint(
                check=Q(validity_range__isempty=False),
                name="validity_range_non_empty",
                violation_error_message="La date de fin de validité doit être supérieure à la date de début",
            ),
            # Prevent two criteria with the same identity from having
            # overlapping validity periods.
            #
            # "perimeter" is part of the identity key because the same
            # (evaluator, activation_map, regulation) combination legitimately
            # exists for different perimeters (e.g. different SAGE zones).
            # Coalesce(perimeter, 0) is needed because perimeter is nullable
            # and PostgreSQL exclusion constraints treat NULL != NULL, so
            # without it two NULL-perimeter rows would never conflict.
            #
            # Coalesce(validity_range, '(,)') treats a NULL validity_range as
            # an infinite range so that an "always valid" criterion correctly
            # conflicts with any other criterion sharing the same identity.
            ExclusionConstraint(
                name="criterion_no_overlapping_validity",
                expressions=[
                    ("evaluator", RangeOperators.EQUAL),
                    ("activation_map", RangeOperators.EQUAL),
                    ("regulation", RangeOperators.EQUAL),
                    (
                        Coalesce("perimeter", Value(0)),
                        RangeOperators.EQUAL,
                    ),
                    (
                        Coalesce(
                            "validity_range",
                            Value(DateRange(None, None, "[)")),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                violation_error_message=(
                    "Ce critère chevauche un critère existant avec le même "
                    "évaluateur, la même carte d'activation et la même réglementation."
                ),
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if (
            self.regulation.regulation in MoulinetteHaie.REGULATIONS
            and not self.activation_mode
        ):
            raise ValidationError(
                {
                    "activation_mode": "Ce champ est obligatoire pour les réglementations du GUH"
                }
            )

    @property
    def slug(self):
        return self.evaluator.slug

    @property
    def unique_slug(self):
        return f"{self.regulation.slug}__{self.slug}"

    def evaluate(self, moulinette, distance):
        """Initialize and run the actual evaluator."""

        # Before the evaluation, let's create a `MoulinetteTemplate` dict
        # It would make more sense to do this in the `__init__` method, but
        # the templates would have not be prefetched yet.
        self._templates = {t.key: t for t in self.templates.all()}

        self.moulinette = moulinette
        self._evaluator = self.evaluator(moulinette, distance, self.evaluator_settings)
        self._evaluator.evaluate()

    def get_evaluator(self):
        """Return the evaluator instance.

        This method is useful because templates cannot access properties starting
        with an underscore.
        """
        return self._evaluator

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

    def should_be_displayed(self):
        """Should the criterion result be displayed?

        When their result is not available, optional criteria should not be displayed.
        """
        if hasattr(self._evaluator, "should_be_displayed"):
            result = self._evaluator.should_be_displayed()
        else:
            result = not (self.is_optional and self.result == RESULTS.non_disponible)
        return result

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

        return self._evaluator.form_class

    def get_form(self):
        if not hasattr(self, "_evaluator"):
            raise RuntimeError("Criterion must be evaluated before accessing the form.")

        return self._evaluator.get_form()

    def get_settings_form(self):
        settings_form_class = getattr(self.evaluator, "settings_form_class", None)
        if settings_form_class:
            if self.evaluator_settings:
                form = settings_form_class(self.evaluator_settings)
            else:
                form = settings_form_class()
        else:
            form = None
        return form

    def get_template(self, template_key):
        return self._templates.get(template_key, None)

    @property
    def result_tag_style(self):
        """Return the criterion result tag style."""
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Criterion must be evaluated before accessing the result code."
            )

        return self._evaluator.result_tag_style

    @property
    def actions_to_take(self) -> set[str]:
        """Get potential actions to take from regulation result."""
        if not hasattr(self, "_evaluator"):
            raise RuntimeError(
                "Criterion must be evaluated before accessing actions to take."
            )

        if hasattr(self._evaluator, "actions_to_take"):
            actions_to_take = set(self._evaluator.actions_to_take)
        else:
            actions_to_take = set()

        return actions_to_take


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
    is_activated = models.BooleanField(
        _("Is activated"),
        help_text=_("Check if all criteria have been set"),
        default=False,
    )
    regulations = models.ManyToManyField(
        "moulinette.Regulation",
        verbose_name=_("Regulations"),
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
    rules_url = models.URLField(_("Rules url"), blank=True)

    class Meta:
        verbose_name = _("Perimeter")
        verbose_name_plural = _("Perimeters")

    def __str__(self):
        return self.name

    def has_contact(self):
        return any(
            (
                self.contact_url,
                self.contact_phone,
                self.contact_email,
            )
        )

    @property
    def contact(self):
        """Format an address string."""
        lines = [f"<strong>{self.contact_name or self.name}</strong>"]
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


class ConfigQuerySet(models.QuerySet):
    """QuerySet for Config models with validity date filtering."""

    def valid_at(self, date):
        """Filter configs valid at the given date.

        A config is valid if its validity_range contains the date,
        or if validity_range is NULL (always valid).
        """
        return self.filter(
            Q(validity_range__contains=date) | Q(validity_range__isnull=True)
        )

    def get_valid_config(self, department, date=None):
        """Get the configuration for a department at a given date."""

        if date is None:
            date = timezone.now().date()
        return self.filter(department=department).valid_at(date).first()


class ConfigBase(models.Model):
    department = models.ForeignKey(
        "geodata.Department",
        verbose_name=_("Department"),
        on_delete=models.PROTECT,
        related_name="%(class)ss",  # Plural: configamenagements, confighaies
    )
    is_activated = models.BooleanField(
        _("Is activated"),
        help_text=_("Is the moulinette available for this department?"),
        default=False,
    )
    validity_range = DateRangeField(
        "Dates de validité",
        blank=True,
        null=True,
    )

    objects = ConfigQuerySet.as_manager()

    class Meta:
        abstract = True
        constraints = [
            CheckConstraint(
                check=Q(validity_range__isempty=False),
                name="%(class)s_validity_range_non_empty",
                violation_error_message=_(
                    "La date de fin de validité doit être supérieure à la date de début."
                ),
            ),
            ExclusionConstraint(
                name="%(class)s_no_overlapping_validity",
                expressions=[
                    ("department", RangeOperators.EQUAL),
                    (
                        Coalesce(
                            "validity_range",
                            Value(DateRange(None, None, "[)")),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                violation_error_message=_(
                    "Cette configuration chevauche une configuration "
                    "existante pour ce département."
                ),
            ),
        ]

    def __str__(self):
        dept_display = self.department.get_department_display()
        if not self.validity_range:
            return dept_display
        lower = self.validity_range.lower
        upper = self.validity_range.upper
        fmt = "%d/%m/%y"
        if lower and upper:
            return f"{dept_display} {lower.strftime(fmt)} → {upper.strftime(fmt)}"
        if lower:
            return f"{dept_display} {lower.strftime(fmt)} → ajd"
        if upper:
            return f"{dept_display} → {upper.strftime(fmt)}"
        return dept_display


class ConfigAmenagement(ConfigBase):
    """Some moulinette content depends on the department.

    This object is dedicated to the Amenagement moulinette. For Haie, see ConfigHaie.
    """

    regulations_available = ArrayField(
        base_field=models.CharField(max_length=64, choices=REGULATIONS),
        blank=True,
        default=list,
    )
    zh_doubt = models.BooleanField("Tout le département en ZH doute", default=False)
    ddtm_water_police_email = models.EmailField(
        "E-mail DDT(M) police de l'eau", blank=True
    )
    ddtm_n2000_email = models.EmailField("E-mail DDT(M) Natura 2000", blank=True)
    dreal_eval_env_email = models.EmailField("E-mail DREAL pôle eval env", blank=True)
    dreal_department_unit_url = models.URLField("Url UD DREAL", blank=True)
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

    ep_free_mention = models.TextField(
        "Espèces protégées > Paragraphe libre", default="", null=False, blank=True
    )

    class Meta(ConfigBase.Meta):
        verbose_name = _("Config amenagement")
        verbose_name_plural = _("Configs amenagement")


def get_hedge_properties_form(type: Literal[TO_PLANT, TO_REMOVE]):
    """Get hedge properties form
    TODO: move this in hedges/forms.py
    """
    self = (
        HedgeToPlantPropertiesForm if type == TO_PLANT else HedgeToRemovePropertiesForm
    )

    return [
        (f"{self.__module__}.{self.__name__}", self.human_readable_name())
        for self in [self] + list(get_subclasses(self))
    ]


class ConfigHaie(ConfigBase):
    """Some moulinette content depends on the department.

    This object is dedicated to the Haie moulinette. For Amenagement, see ConfigAmenagement.
    """

    regulations_available = ArrayField(
        base_field=models.CharField(max_length=64, choices=REGULATIONS),
        blank=True,
        default=list,
    )
    single_procedure = models.BooleanField(
        "Régime unique",
        default=False,
        help_text="Le régime unique s'applique dans ce département",
    )
    single_procedure_settings = models.JSONField(
        "Paramètres du régime unique",
        blank=True,
        null=False,
        default=dict,
    )

    department_doctrine_html = models.TextField(
        "Champ html doctrine département", blank=True
    )

    contacts_and_links = models.TextField(
        "Champ html d’information fléchage", blank=True
    )

    hedge_maintenance_html = models.TextField("Champ html pour l’entretien", blank=True)

    natura2000_coordinators_list_url = models.URLField(
        "URL liste des animateurs Natura 2000", blank=True
    )

    hedge_to_plant_properties_form = models.CharField(
        "Caractéristiques demandées pour les haies à planter",
        choices=get_hedge_properties_form(TO_PLANT),
        max_length=256,
        default=f"{HedgeToPlantPropertiesForm.__module__}.{HedgeToPlantPropertiesForm.__name__}",
    )

    hedge_to_remove_properties_form = models.CharField(
        "Caractéristiques demandées pour les haies à détruire",
        choices=get_hedge_properties_form(TO_REMOVE),
        max_length=256,
        default=f"{HedgeToRemovePropertiesForm.__module__}.{HedgeToRemovePropertiesForm.__name__}",
    )

    demarche_simplifiee_number = models.IntegerField(
        "Numéro de la démarche DS",
        blank=True,
        null=True,
        help_text="Vous trouverez ce numéro en haut à droite de la carte de votre démarche dans la liste suivante : "
        '<a href="https://www.demarches-simplifiees.fr/admin/procedures" target="_blank" rel="noopener">'
        "https://www.demarches-simplifiees.fr/admin/procedures</a>",
    )

    demarche_simplifiee_pre_fill_config = models.JSONField(
        "Configuration pré-remplissage DS",
        blank=True,
        null=False,
        default=list,
    )

    demarches_simplifiees_display_fields = models.JSONField(
        blank=True,
        null=False,
        default=dict,
    )

    demarches_simplifiees_city_id = models.CharField(
        'Identifiant DS "Commune principale"',
        blank=True,
        max_length=64,
    )

    demarches_simplifiees_organization_id = models.CharField(
        'Identifiant DS "Nom de votre structure"',
        blank=True,
        max_length=64,
    )

    demarches_simplifiees_pacage_id = models.CharField(
        'Identifiant DS "numéro de PACAGE"',
        blank=True,
        max_length=64,
    )

    demarches_simplifiees_project_url_id = models.CharField(
        'Identifiant DS "Lien internet de la simulation réglementaire de votre projet"',
        blank=True,
        max_length=64,
    )

    def __str__(self):
        return self.department.get_department_display()

    def clean(self):
        super().clean()
        if self.is_activated and self.demarche_simplifiee_pre_fill_config is not None:
            # add constraints on the pre-fill configuration json to avoid unexpected entries

            if not isinstance(self.demarche_simplifiee_pre_fill_config, list):
                raise ValidationError(
                    {
                        "demarche_simplifiee_pre_fill_config": "Cette configuration doit être une liste de champs"
                        " (ou d'annotations privées) à pré-remplir"
                    }
                )

            availables_sources = {
                tup[0]
                for value in self.get_demarche_simplifiee_value_sources().values()
                for tup in value
            }
            for field in self.demarche_simplifiee_pre_fill_config:
                if (
                    not isinstance(field, dict)
                    or "id" not in field
                    or "value" not in field
                ):
                    raise ValidationError(
                        {
                            "demarche_simplifiee_pre_fill_config": "Chaque champ (ou annotation privée) doit contenir"
                            " au moins l'id côté Démarches Simplifiées et la "
                            "source de la valeur côté guichet unique de la haie."
                        }
                    )
                if field["value"] not in availables_sources:
                    raise ValidationError(
                        {
                            "demarche_simplifiee_pre_fill_config": f"La source de la valeur {field['value']} n'est pas "
                            f"valide pour le champ dont l'id est {field['id']}"
                        }
                    )
                if "mapping" in field and not isinstance(field["mapping"], dict):
                    raise ValidationError(
                        {
                            "demarche_simplifiee_pre_fill_config": f"Le mapping du champ dont l'id est {field['id']} "
                            f"doit être un dictionnaire."
                        }
                    )

    @classmethod
    def get_demarche_simplifiee_value_sources(cls):
        """Populate a list of available sources for the pre-fill configuration of the demarche simplifiee

        This method aggregates :
         * some well known values (e.g. moulinette_url)
         * the fields of all the forms that the user may have to fill in the guichet unique de la haie :
            * the main form
            * the triage form
            * the forms of the criteria of involved regulations
         * the results of the regulations
        """

        regulations = Regulation.objects.filter(
            regulation__in=MoulinetteHaie.REGULATIONS
        ).prefetch_related("criteria")
        triage_form_fields = {
            (key, field.label) for key, field in TriageFormHaie.base_fields.items()
        }
        main_form_fields = {
            (key, field.label)
            for key, field in MoulinetteHaie.main_form_class.base_fields.items()
        }

        identified_sources = {
            ("url_moulinette", "Url de la simulation"),
            ("url_projet", "Url du projet de dossier"),
            ("ref_projet", "Référence du projet de dossier"),
            (
                "plantation_adequate",
                "Les conditions d’acceptabilité de la plantation sont toutes respectées (booléen)",
            ),
            ("vieil_arbre", "Présence de vieux arbres fissurés ou à cavité (booléen)"),
            ("proximite_mare", "Proximité d'une mare (booléen)"),
            (
                "sur_talus_d",
                "Au moins une haie à détruire est marquée “sur_talus” (booléen)",
            ),
            (
                "sur_talus_p",
                "Au moins une haie à planter est marquée “sur_talus” (booléen)",
            ),
        }

        available_sources = {
            "Fléchage": triage_form_fields,
            "Questions principales": main_form_fields,
        }

        regulation_results = set()
        criteria_results = set()

        for regulation in regulations.all():
            regulation_sources = set()
            regulation_results.add(
                (
                    f"{regulation.slug}.result",
                    f"Résultat de la réglementation {regulation.regulation}",
                )
            )
            for criterion in regulation.criteria.all():
                criteria_results.add(
                    (
                        f"{regulation.slug}.{criterion.slug}.result_code",
                        f"Code de résultat du critère {criterion.backend_title} de la "
                        f"réglementation {regulation.regulation}",
                    )
                )
                form_class = criterion.evaluator.form_class
                if form_class:
                    regulation_sources.update(
                        {
                            (key, field.label)
                            for key, field in form_class.base_fields.items()
                        }
                    )

            if regulation_sources:
                available_sources[f'Questions complémentaires "{regulation.title}"'] = (
                    regulation_sources
                )

        available_sources["Résultats réglementation"] = regulation_results
        available_sources["Résultats des critères"] = criteria_results
        available_sources["Variables projet"] = identified_sources

        return available_sources

    class Meta(ConfigBase.Meta):
        verbose_name = "Config haie"
        verbose_name_plural = "Configs haie"
        constraints = ConfigBase.Meta.constraints + [
            CheckConstraint(
                check=Q(is_activated=False)
                | Q(demarche_simplifiee_number__isnull=False),
                name="demarche_simplifiee_number_required_if_activated",
            ),
            CheckConstraint(
                check=Q(demarche_simplifiee_number__isnull=True)
                | Q(demarches_simplifiees_project_url_id__isnull=False),
                name="project_url_id_required_if_demarche_number",
            ),
            CheckConstraint(
                name="single_procedure_requires_coeff_compensation",
                violation_error_message="Les paramètres de régime unique doivent comporter des coefficients de "
                "compensation numérique pour chaque type de haies (degradee, buissonnante, "
                "arbustive et mixte).",
                check=Q(single_procedure=False)
                | (
                    Q(single_procedure_settings__has_key="coeff_compensation")
                    & Q(
                        single_procedure_settings__coeff_compensation__has_key="degradee"
                    )
                    & Q(
                        single_procedure_settings__coeff_compensation__degradee__regex=r"^\d+(\.\d+)?$"
                    )
                    & Q(
                        single_procedure_settings__coeff_compensation__has_key="buissonnante"
                    )
                    & Q(
                        single_procedure_settings__coeff_compensation__buissonnante__regex=r"^\d+(\.\d+)?$"
                    )
                    & Q(
                        single_procedure_settings__coeff_compensation__has_key="arbustive"
                    )
                    & Q(
                        single_procedure_settings__coeff_compensation__arbustive__regex=r"^\d+(\.\d+)?$"
                    )
                    & Q(single_procedure_settings__coeff_compensation__has_key="mixte")
                    & Q(
                        single_procedure_settings__coeff_compensation__mixte__regex=r"^\d+(\.\d+)?$"
                    )
                ),
            ),
        ]


TEMPLATE_KEYS = [
    "autorisation_urba_pa",
    "autorisation_urba_pa_lotissement",
    "autorisation_urba_pc",
    "autorisation_urba_amenagement_dp",
    "autorisation_urba_construction_dp",
    "autorisation_urba_none",
    "autorisation_urba_other",
]


def get_all_template_keys():
    tpls = TEMPLATE_KEYS + list(list_moulinette_templates())
    return zip(tpls, tpls)


class MoulinetteTemplate(models.Model):
    """A custom moulinette template that can be admin edited.

    Templates can be associated to departments (through ConfigAmenagement) or
    criteria.
    """

    config = models.ForeignKey(
        "moulinette.ConfigAmenagement",
        verbose_name=_("Config"),
        on_delete=models.PROTECT,
        related_name="templates",
        null=True,
    )
    criterion = models.ForeignKey(
        "moulinette.Criterion",
        verbose_name=_("Criterion"),
        on_delete=models.PROTECT,
        related_name="templates",
        null=True,
    )
    key = models.CharField(_("Key"), choices=get_all_template_keys(), max_length=512)
    content = models.TextField(_("Content"), blank=True, default="")

    class Meta:
        verbose_name = _("Moulinette template")
        verbose_name_plural = _("Moulinette templates")
        constraints = [
            # Make sure the template is associated with a single related object
            models.CheckConstraint(
                check=Q(config__isnull=False, criterion=None)
                | Q(criterion__isnull=False, config=None),
                name="relation_to_single_object",
            ),
            # Make sure each criterion / config cannot have duplicate templates
            models.UniqueConstraint(
                fields=["config", "key"],
                condition=Q(config__isnull=False),
                name="unique_template_config_key",
            ),
            models.UniqueConstraint(
                fields=["criterion", "key"],
                condition=Q(criterion__isnull=False),
                name="unique_template_criterion_key",
            ),
        ]


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


class Moulinette(ABC):
    """Automatic environment law evaluation processing tool.

    Given a bunch of relevant user provided data, we try to perform an
    automatic computation and tell if the project is subject to the Water Law
    or other regulations.
    """

    _is_evaluated = False

    REGULATIONS = [
        "loi_sur_leau",
        "natura2000",
        "eval_env",
        "sage",
        "conditionnalite_pac",
        "ep",
        "alignement_arbres",
    ]

    def __init__(self, form_kwargs):
        self.catalog = MoulinetteCatalog()
        # Maybe here department should be evaluated if existing
        if "initial" in form_kwargs:
            form_kwargs["initial"].update(compute_surfaces(form_kwargs["initial"]))
        if "data" in form_kwargs:
            form_kwargs["data"].update(compute_surfaces(form_kwargs["data"]))
        self.form_kwargs = form_kwargs
        self.catalog = self.get_catalog_data()
        if self.bound_main_form.is_valid():
            if self.config and self.config.id and hasattr(self.config, "templates"):
                self.templates = {t.key: t for t in self.config.templates.all()}
            else:
                self.templates = {}

            self.evaluate()

    def evaluate(self):
        for regulation in self.regulations:
            regulation.evaluate(self)
        self._is_evaluated = True

    def is_evaluated(self):
        return self._is_evaluated

    @cached_property
    def department(self):
        return self.get_department()

    @cached_property
    def config(self):
        return self.get_config()


    def get_main_form(self):
        """Return the instanciated main moulinette form."""

        return self.get_main_form_class()(**self.form_kwargs)

    @cached_property
    def main_form(self):
        return self.get_main_form()

    @cached_property
    def bound_main_form(self):
        """Get the main form with forced bound data.

        When we display the moulinette form, we show the main form with
        initial values. But if the initial data would be valid data, then we
        want to also display the additional forms.

        In that case, we force a form validation by creating a moulinette form
        where we pass initial data as validation data.
        """
        if self.main_form.is_bound:
            return self.main_form
        else:
            form_kwargs = self.form_kwargs.copy()
            form_kwargs["data"] = form_kwargs.get("initial", {})
            bound_form = self.get_main_form_class()(**form_kwargs)
            return bound_form

    def get_triage_form(self):
        """Return the instanciated triage form, or None if no triage is required."""

        TriageForm = self.get_triage_form_class()
        form = TriageForm(**self.form_kwargs) if TriageForm else None
        return form

    @cached_property
    def triage_form(self):
        return self.get_triage_form()

    @cached_property
    def bound_triage_form(self):
        if self.triage_form.is_bound:
            return self.triage_form
        else:
            form_kwargs = self.form_kwargs.copy()
            form_kwargs["data"] = form_kwargs.get("initial", {})
            bound_form = self.get_triage_form_class()(**form_kwargs)
            return bound_form

    def get_additional_forms(self):
        """Get a list of instanciated additional questions forms.

        Additional forms are questions that conditionaly arrise depending on the data
        from the main form.

        We can only build this list if the main form is filled and valid.
        """
        forms = []

        if not self.is_evaluated():
            return forms

        form_classes = self.additional_form_classes()
        for form_class in form_classes:
            form = form_class(**self.form_kwargs)

            # Some forms end up with no fields, depending on the project data
            # so we just skip them
            if form.fields:
                forms.append(form)
        return forms

    def additional_form_classes(self):
        """Return the list of forms for additional questions.

        Some criteria need more data to return an answer. Here, we gather all
        the forms to gather this data.
        """

        form_classes = []

        for regulation in self.regulations:
            for criterion in regulation.criteria.all():
                if not criterion.is_optional:
                    form_class = criterion.get_form_class()
                    if form_class and form_class not in form_classes:
                        form_classes.append(form_class)

        return form_classes

    @cached_property
    def additional_forms(self):
        return self.get_additional_forms()

    def get_optional_forms(self):
        """Get a list of instanciated optional forms.

        Optional forms can be selectively activated during a simulation.

        There are two cases:
         - if the main form is valid, we can fetch the active criteria, and get the
           specific list of associated optional forms.
         - otherwise, we just find all optional criteria that are associated with
           the moulinette regulations.
        """
        forms = []
        form_classes = self.optional_form_classes()

        for form_class in form_classes:
            # Every optional form has a "activate" field
            # If unchecked, the form validation must be ignored alltogether
            activate_field = f"{form_class.prefix}-activate"
            form_kwargs = self.form_kwargs.copy()
            if "data" in form_kwargs and activate_field not in form_kwargs["data"]:
                form_kwargs.pop("data")

            form = form_class(**form_kwargs)

            # We skip optional forms that were not activated
            if form.is_bound and hasattr(form, "is_activated"):
                form.full_clean()
                if not form.is_activated():
                    continue

            if form.fields:
                forms.append(form)
        return forms

    def optional_form_classes(self):
        """Return the list of forms for optional questions.

        If the moulinette is bound, we can fetch the precise optional criterion list and
        get their forms.

        Otherwise, we have to fetch every single existing optional criterion.
        """
        form_classes = []

        if self.is_evaluated():
            for regulation in self.regulations:
                for criterion in regulation.criteria.all():
                    if criterion.is_optional:
                        form_class = criterion.get_form_class()
                        if form_class and form_class not in form_classes:
                            form_classes.append(form_class)
        else:
            for criterion in self.get_optional_criteria():
                form_class = criterion.evaluator.form_class
                if form_class and form_class not in form_classes:
                    form_classes.append(form_class)

        return form_classes

    @cached_property
    def optional_forms(self):
        return self.get_optional_forms()

    def get_all_forms(self):
        """Return all forms associated with the Moulinette."""

        all_forms = [self.main_form]
        all_forms.extend(self.additional_forms)
        all_forms.extend(self.optional_forms)

        triage_form = self.get_triage_form()
        if triage_form:
            all_forms.append(triage_form)

        return all_forms

    @property
    def all_forms(self):
        return self.get_all_forms()

    def get_prefixed_fields(self):
        """Return all known fields, with prefixed keys."""

        forms = self.all_forms
        fields = {}
        for form in forms:
            for k, v in form.fields.items():
                fields[form.add_prefix(k)] = v
        return fields

    @property
    def initial(self):
        """Return the moulinette initial data."""

        return self.form_kwargs.get("initial", {})

    @property
    def data(self):
        """Return the moulinette raw form data."""

        return self.form_kwargs.get("data", {})

    @property
    def cleaned_data(self):
        """Return the moulinette data as cleaned by all existing forms."""

        data = {}
        for form in self.all_forms:
            form.full_clean()
            if hasattr(form, "prefixed_cleaned_data"):
                data.update(form.prefixed_cleaned_data)
            elif hasattr(form, "cleaned_data"):
                data.update(form.cleaned_data)
        return data

    def form_errors(self):
        """Return the list of all form validation errors."""

        errors = {}
        for form in self.get_all_forms():
            form.full_clean()
            for k, v in form.errors.items():
                errors[k] = v
        return errors

    def is_valid(self):
        """The moulinette is valid if it can run the evaluation.
        - the main form is valid
        - all additional required forms are valid
        - all activated optional forms are valid
        """
        return self.main_form.is_valid() and not bool(self.form_errors())

    def has_missing_data(self):
        """Make sure all the data required to compute the result is provided."""

        return bool(self.form_errors())

    def cleaned_additional_data(self):
        """Return combined additional data from custom criterion forms."""

        data = {}
        for form in self.additional_forms:
            if form.is_valid():
                data.update(form.cleaned_data)

        return data

    @cached_property
    def additional_fields(self):
        """Get a {field_name: field} dict of all additional questions fields."""

        fields = OrderedDict()
        for form in self.additional_forms:
            for field in form:
                if field.name not in fields:
                    fields[field.name] = field
        return fields

    def are_additional_forms_bound(self):
        """Return true if some additional forms received any data."""

        data = self.data
        return any(key in data for key in self.additional_fields.keys())

    @cached_property
    def optional_fields(self):
        """Get a {field_name: field} dict of all optional questions fields."""

        fields = OrderedDict()
        for form in self.optional_forms:
            for field in form:
                field_name = form.add_prefix(field.name)
                if field_name not in fields:
                    fields[field_name] = field
        return fields

    def are_optional_forms_bound(self):
        """Return true if some optional forms received any data."""

        data = self.data
        return any(key in data for key in self.optional_fields.keys())

    @property
    def regulations(self):
        if not hasattr(self, "_regulations"):
            self._regulations = self.get_regulations()
        return self._regulations

    @regulations.setter
    def regulations(self, value):
        self._regulations = value

    def has_config(self):
        """Check if a valid, active config exists for this department."""
        return bool(self.config)

    @abstractmethod
    def get_config(self):
        pass

    def get_template(self, template_key):
        """Return the MoulinetteTemplate with the given key."""

        return self.templates.get(template_key, None)

    def get_home_template(self):
        """Return the template to display the result page."""

        if not hasattr(self, "home_template"):
            raise AttributeError("No result template found.")
        return self.home_template

    def get_result_template(self):
        """Return the template to display the result page."""

        if not hasattr(self, "result_template"):
            raise AttributeError("No result template found.")
        return self.result_template

    def get_debug_result_template(self):
        """Return the template to display the result page."""

        if not hasattr(self, "debug_result_template"):
            raise AttributeError("No result template found.")
        return self.debug_result_template

    def get_result_non_disponible_template(self):
        """Return the template to display the result_non_disponible page."""

        if not hasattr(self, "result_non_disponible"):
            raise AttributeError("No result_non_disponible template found.")
        return self.result_non_disponible

    def get_result_available_soon_template(self):
        """Return the template to display the result_available_soon page."""

        if not hasattr(self, "result_available_soon"):
            raise AttributeError("No result_available_soon template found.")
        return self.result_available_soon

    def get_main_form_class(self):
        """Return the form class for the main questions."""

        if not hasattr(self, "main_form_class"):
            raise AttributeError("No main form class found.")
        return self.main_form_class

    def get_triage_form_class(self):
        """Return the triage form.

        Triage is optional, so we don't raise error if no form class is defined.
        """
        return getattr(self, "triage_form_class", None)

    def get_criteria(self):
        """Fetch relevant criteria for evaluation.

        We don't actually use the criteria directly, the returned queryset will only
        be used in a prefetch_related call when we fetch the regulations.
        """
        criteria = (
            Criterion.objects.valid_at(self.date)
            .order_by("weight")
            .distinct("weight", "id")
            .prefetch_related("templates")
            .annotate(distance=Cast(0, IntegerField()))
            .order_by("weight", "id", "distance")
        )

        return criteria

    def get_optional_criteria(self):
        """Fetch optional criteria used by this moulinette regulations."""
        criteria = Criterion.objects.filter(
            is_optional=True, regulation__regulation__in=self.REGULATIONS
        ).order_by("weight")

        return criteria

    def get_regulations(self):
        """Find the activated regulations and their criteria."""

        criteria = self.get_criteria()
        regulations = (
            Regulation.objects.filter(regulation__in=self.REGULATIONS)
            .order_by("weight")
            .prefetch_related(Prefetch("criteria", queryset=criteria))
        )
        return regulations

    def get_catalog_data(self):
        """Populate the catalog with any needed data."""

        self.bound_main_form.full_clean()
        catalog = MoulinetteCatalog(**self.bound_main_form.cleaned_data)
        return catalog

    def is_evaluation_available(self):
        return self.config and self.config.is_activated and self.is_valid()

    def __getattr__(self, attr):
        """Returns the corresponding regulation.

        Allows to do something like this:
        moulinette.loi_sur_leau to fetch the correct regulation.
        """
        if attr in self.REGULATIONS:
            return self.get_regulation(attr)
        else:
            return getattr(super(), attr)

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

    def summary_fields(self):
        """Return the fields displayed in "Caractéristiques du projet" sidebar section."""
        fields = self.additional_fields
        return fields

    @abstractmethod
    def summary(self):
        """Build a data summary, for analytics purpose."""
        raise NotImplementedError

    @property
    def result(self):
        """Compute global result from individual regulation results.

        There is no such thing as a "global simulation result", since a result
        is a regulation level concept.

        So this method returns a code that will be used to select the main template
        of the moulinette result page. It is also used to select the evaluation email
        template.

        The name will be refactored eventually.
        """

        # return the cached result if it was overriden
        # Otherwise, we don't cache the result because it can change between invocations
        if hasattr(self, "_result"):
            return self._result

        if not self.is_evaluated():
            self._result = RESULTS.non_disponible
            return self._result

        results = [regulation.result for regulation in self.regulations]

        result = None
        for cascading_result in RESULT_CASCADE:
            if cascading_result in results:
                result = GLOBAL_RESULT_MATRIX[cascading_result]
                break

        return result or RESULTS.non_soumis

    @result.setter
    def result(self, value):
        """Allow monkeypatching moulinette result for tests."""
        self._result = value

    @property
    def result_tag_style(self):
        """Compute global result tag style."""
        return TAG_STYLES_BY_RESULT[self.result]

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

    def get_form_template(self):
        """Return the template name for the moulinette."""

        if not hasattr(self, "form_template"):
            raise AttributeError("No form template name found.")
        return self.form_template

    @abstractmethod
    def get_debug_context(self):
        """Add some data to display on the debug page"""
        raise NotImplementedError

    @abstractmethod
    def get_triage_params(self):
        """Add some data to display on the debug page"""
        raise NotImplementedError

    def is_triage_valid(self):
        return True

    def get_extra_context(self, request):
        """return extra context data for the moulinette views.
        You can use this method to add some context specific to your site : Haie or Amenagement
        """

        return {
            "department": self.department,
            "config": self.config,
        }

    def get_map_center(self):
        """Returns at what coordinates the perimeter."""
        raise NotImplementedError

    @cached_property
    def actions_to_take(self):
        """Get potential actions to take from all activated regulations and criteria"""
        actions_to_take = set()
        for regulation in self.regulations:
            actions_to_take.update(regulation.actions_to_take)
            for criterion in regulation.criteria.all():
                actions_to_take.update(criterion.actions_to_take)

        actions = ActionToTake.objects.filter(slug__in=actions_to_take).all()
        result = defaultdict(list)
        for action in actions:
            action_key = action.type if action.type == "pc" else action.target
            result[action_key].append(action)
        return dict(result)

    @cached_property
    def date(self):
        """Date for the simulation. Today by default."""
        date_str = self.data.get("date") or self.initial.get("date")
        if date_str:
            try:
                return parser.isoparse(date_str).date()
            except (ValueError, TypeError):
                pass
        return date.today()


class MoulinetteAmenagement(Moulinette):
    REGULATIONS = ["loi_sur_leau", "natura2000", "eval_env", "sage"]
    home_template = "amenagement/moulinette/home.html"
    result_template = "amenagement/moulinette/result.html"
    debug_result_template = "amenagement/moulinette/result_debug.html"
    result_available_soon = "amenagement/moulinette/result_available_soon.html"
    result_non_disponible = "amenagement/moulinette/result_non_disponible.html"
    form_template = "amenagement/moulinette/form.html"
    main_form_class = MoulinetteFormAmenagement
    triage_form_class = None

    def get_regulations(self):
        """Find the activated regulations and their criteria."""

        perimeters = self.get_perimeters()

        regulations = (
            super()
            .get_regulations()
            .prefetch_related(Prefetch("perimeters", queryset=perimeters))
        )
        return regulations

    def get_perimeters(self):
        coords = self.catalog["lng_lat"]
        zones = self.catalog["all_zones"]

        perimeters = (
            Perimeter.objects.filter(activation_map__zones__in=zones)
            .annotate(geometry=F("activation_map__geometry"))
            .annotate(
                distance=Cast(
                    Distance("activation_map__zones__geometry", coords), IntegerField()
                )
            )
            .order_by("id", "distance")
            .distinct("id")
            .select_related("activation_map")
            .defer("activation_map__geometry")
        )

        return perimeters

    def get_criteria(self):
        coords = self.catalog["lng_lat"]
        zones = self.catalog["all_zones"]

        criteria = (
            super()
            .get_criteria()
            .filter(activation_map__zones__in=zones)
            .annotate(
                distance=Cast(
                    Distance("activation_map__zones__geometry", coords), IntegerField()
                )
            )
            .filter(distance__lte=F("activation_distance"))
            .select_related("activation_map")
            .defer("activation_map__geometry")
        )

        return criteria

    def get_catalog_data(self):
        """Fetch / compute data required for further computations."""

        catalog = super().get_catalog_data()
        if "lat" in catalog and "lng" in catalog:

            lng = catalog["lng"]
            lat = catalog["lat"]
            catalog["lng_lat"] = Point(float(lng), float(lat), srid=EPSG_WGS84)
            catalog["coords"] = catalog["lng_lat"].transform(EPSG_MERCATOR, clone=True)
            catalog["circle_12"] = catalog["coords"].buffer(12)
            catalog["circle_25"] = catalog["coords"].buffer(25)
            catalog["circle_100"] = catalog["coords"].buffer(100)

            fetching_radius = int(self.data.get("radius", "200"))
            zones = self.get_zones(catalog["lng_lat"], fetching_radius)
            catalog["all_zones"] = zones

            def wetlands_filter(zone):
                return all(
                    (
                        zone.map.map_type == "zone_humide",
                        zone.map.data_type in ("certain", "forbidden"),
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

            catalog["potential_wetlands"] = list(
                filter(potential_wetlands_filter, zones)
            )

            def forbidden_wetlands_filter(zone):
                return all(
                    (
                        zone.map.map_type == "zone_humide",
                        zone.map.data_type == "forbidden",
                    )
                )

            catalog["forbidden_wetlands"] = list(
                filter(forbidden_wetlands_filter, zones)
            )

            def flood_zones_filter(zone):
                return all(
                    (
                        zone.map.map_type == "zone_inondable",
                        zone.map.data_type == "certain",
                    )
                )

            catalog["flood_zones"] = list(filter(flood_zones_filter, zones))

            def potential_flood_zones_filter(zone):
                return all(
                    (
                        zone.map.map_type == "zone_inondable",
                        zone.map.data_type == "uncertain",
                    )
                )

            catalog["potential_flood_zones"] = list(
                filter(potential_flood_zones_filter, zones)
            )

        return catalog

    def get_zones(self, coords, radius=200):
        """Return the Zone objects containing the queried coordinates."""

        zones = (
            Zone.objects.filter(geometry__dwithin=(coords, D(m=radius)))
            .annotate(distance=Cast(Distance("geometry", coords), IntegerField()))
            .annotate(geom=Cast("geometry", MultiPolygonField()))
            .select_related("map")
            .defer("map__geometry")
            .order_by("distance", "map__name")
        )
        return zones

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
            summary["main_result"] = self.result

        return summary

    def get_department(self):
        if "lng_lat" not in self.catalog:
            return None

        lng_lat = self.catalog["lng_lat"]
        department = Department.objects.filter(geometry__contains=lng_lat).first()
        return department

    def get_config(self):
        if not self.department:
            return None
        config = ConfigAmenagement.objects.prefetch_related(
            "templates"
        ).get_valid_config(self.department, self.date)
        return config

    def get_debug_context(self):
        # In the debug page, we want to factorize the maps we display, so we order them
        # by map first
        return {
            "grouped_perimeters": self.get_perimeters()
            .order_by(
                "activation_map__name",
                "id",
                "distance",
            )
            .distinct("activation_map__name", "id"),
            "grouped_criteria": self.get_criteria()
            .annotate(
                geometry=F("activation_map__zones__geometry"),
            )
            .order_by(
                "activation_map__name",
                "id",
                "distance",
            )
            .distinct("activation_map__name", "id"),
            "grouped_zones": (
                self.catalog["all_zones"]
                .annotate(type=Concat("map__map_type", V("-"), "map__data_type"))
                .order_by("type", "distance", "map__name")
            ),
        }

    def get_triage_params(self):
        return set()

    def get_map_center(self):
        """Returns at what coordinates the perimeter."""
        return self.catalog["lng_lat"]


class MoulinetteHaie(Moulinette):
    REGULATIONS = [
        "conditionnalite_pac",
        "ep",
        "natura2000_haie",
        "alignement_arbres",
        "urbanisme_haie",
        "reserves_naturelles",
        "code_rural_haie",
        "regime_unique_haie",
        "sites_proteges_haie",
        "sites_inscrits_haie",
        "sites_classes_haie",
    ]
    home_template = "haie/moulinette/home.html"
    result_template = "haie/moulinette/result.html"
    debug_result_template = "haie/moulinette/result_debug.html"
    result_available_soon = "haie/moulinette/result_non_disponible.html"
    result_non_disponible = "haie/moulinette/result_non_disponible.html"
    form_template = "haie/moulinette/form.html"
    main_form_class = MoulinetteFormHaie
    triage_form_class = TriageFormHaie

    def get_config(self):
        if not self.department:
            return None
        return ConfigHaie.objects.get_valid_config(
            self.department, self.date
        )

    @property
    def result(self):
        """Compute global result from individual regulation results."""

        if not self.config.single_procedure:
            return super().result

        # return the cached result if it was overriden
        # Otherwise, we don't cache the result because it can change between invocations
        if hasattr(self, "_result"):
            return self._result

        procedures = [regulation.procedure_type for regulation in self.regulations]
        is_interdit = "interdit" in procedures
        is_autorisation = "autorisation" in procedures

        # Check if we are in the "100% alignement d'arbres" case
        hedges = self.catalog["haies"].hedges_filter("TO_REMOVE", "!alignement")
        alignement_arbres = len(hedges) == 0

        if is_interdit:
            result = RESULTS.interdit
        elif alignement_arbres:
            result = "hors_regime_unique"
        elif is_autorisation:
            result = "autorisation"
        else:
            result = "declaration"

        return result or RESULTS.non_soumis

    def summary(self):
        """Build a data summary, for analytics purpose."""
        summary = self.data.copy()
        summary.update(self.cleaned_additional_data())

        if self.is_evaluation_available():
            summary["result"] = self.result_data()
            summary["main_result"] = self.result
            summary["regime_type"] = "ru" if self.config.single_procedure else "dc"

        if "haies" in self.catalog:
            haies = self.catalog["haies"]
            summary["longueur_detruite"] = haies.length_to_remove()
            summary["longueur_plantee"] = haies.length_to_plant()
            hedge_centroid_coords = haies.get_centroid_to_remove()
            summary["lnglat_centroide_haie_detruite"] = (
                f"{hedge_centroid_coords.x}, {hedge_centroid_coords.y}"
            )
            summary["dept_haie_detruite"] = haies.get_department()

        return summary

    def get_debug_context(self):
        context = {}
        if "haies" in self.catalog and self.requires_hedge_density:
            haies = self.catalog["haies"]

            pre_computed_density = haies.density
            if pre_computed_density:
                context.update(
                    {
                        "pre_computed_density_200": pre_computed_density["density_200"],
                        "pre_computed_density_5000": pre_computed_density[
                            "density_5000"
                        ],
                    }
                )

            density_200, density_5000, centroid_geos = (
                haies.compute_density_with_artifacts()
            )
            truncated_circle_200 = density_200["artifacts"].pop("truncated_circle")
            truncated_circle_5000 = density_5000["artifacts"].pop("truncated_circle")

            context.update(
                {
                    "length_200": density_200["artifacts"]["length"],
                    "length_5000": density_5000["artifacts"]["length"],
                    "area_200_ha": density_200["artifacts"]["area_ha"],
                    "area_5000_ha": density_5000["artifacts"]["area_ha"],
                    "density_200": density_200["density"],
                    "density_5000": density_5000["density"],
                }
            )

            # Create the density map
            from envergo.hedges.services import create_density_map

            density_map = create_density_map(
                centroid_geos,
                haies.hedges_to_remove(),
                truncated_circle_200,
                truncated_circle_5000,
            )
            context["density_map"] = density_map

        return context

    def get_triage_params(self):
        return set(TriageFormHaie.base_fields.keys())

    def is_triage_valid(self):
        """Should the triage params allow to go to next step?."""

        triage_form = self.bound_triage_form
        if not triage_form.is_valid():
            return False

        element = triage_form.cleaned_data.get("element")
        travaux = triage_form.cleaned_data.get("travaux")
        return element == "haie" and travaux == "destruction"

    def get_triage_result_template(self):
        """Return the template to display the triage out of scope result."""
        if (
            self.triage_form["element"].value() == "haie"
            and self.triage_form["travaux"].value() != "destruction"
        ):
            return "haie/moulinette/entretien_haies_result.html"

        return "haie/moulinette/triage_result.html"

    def get_extra_context(self, request):
        """return extra context data for the moulinette views.
        You can use this method to add some context specific to your site : Haie or Amenagement
        """
        context = super().get_extra_context(request)
        context["is_alternative"] = bool(request.GET.get("alternative", False))

        if self.config:
            context["hedge_maintenance_html"] = self.config.hedge_maintenance_html

        hedge_id = None
        hedge_data = None
        if "haies" in request.GET and request.method == "GET":
            hedge_id = request.GET["haies"]
        elif "haies" in request.POST and request.method == "POST":
            hedge_id = request.POST["haies"]
        if hedge_id:
            try:
                hedge_data = HedgeData.objects.get(id=hedge_id)
            except HedgeData.DoesNotExist:
                pass

        context["hedge_data"] = hedge_data
        # Fetch all the regulations that have perimeters intersected by hedges to plant but not hedges to remove
        # For single procedure moulinette, filter the regulations that cannot switch the result to "autorisation"
        context["hedges_to_plant_intersecting_regulations_perimeter"] = {
            regulation: hedges[TO_PLANT]
            for regulation, perimeters in self.hedges_intersecting_regulations_perimeter.items()
            for perimeter, hedges in perimeters.items()
            if (
                TO_PLANT in hedges
                and TO_REMOVE not in hedges
                and (
                    not self.config.single_procedure
                    or isinstance(regulation.get_evaluator(), HaieRegulationEvaluator)
                    and "autorisation"
                    in regulation.get_evaluator().PROCEDURE_TYPE_MATRIX.values()
                )
            )
        }

        return context

    def get_catalog_data(self):
        """Fetch / compute data required for further computations."""

        data = super().get_catalog_data()
        # TODO check if this goes in extra context
        if "haies" in data:
            hedges = data["haies"]
            data["has_hedges_outside_department"] = (
                hedges.has_hedges_outside_department(self.department)
            )

        return data

    def get_department(self):
        dept = self.data.get("department", self.initial.get("department", None))
        if dept is None:
            return None

        qs = (
            Department.objects.defer("geometry")
            .annotate(centroid=Centroid("geometry"))
            .filter(department=dept)
        )
        return qs.first()

    def get_regulations(self):
        """Find the activated regulations and their criteria."""
        perimeters = self.get_perimeters()

        regulations = (
            super()
            .get_regulations()
            .prefetch_related(Prefetch("perimeters", queryset=perimeters))
        )
        return regulations

    def get_perimeters(self):
        """Fetch the perimeters that are intersecting at least one hedge (either to remove or to plant)

        Contrary to the criteria, using the department's centroid as a basis does not make sense for the perimeters.
        """
        hedges = self.catalog["haies"].hedges() if "haies" in self.catalog else []
        if hedges:
            zone_subquery = self.get_zone_subquery(hedges)
            perimeters = (
                Perimeter.objects.annotate(
                    distance=Value(
                        0, output_field=IntegerField()
                    )  # We use an exists subquery that check for intersection so the distance is 0
                )
                .annotate(geometry=F("activation_map__geometry"))
                .filter(Exists(zone_subquery))
                .order_by("id")
                .distinct("id")
            )
        else:
            # if there is no hedge in the project
            # no perimeters can be activated as we do not know where the project will be.
            perimeters = Perimeter.objects.none()

        return perimeters

    def get_criteria(self):
        """Fetch the criteria that can be activated for this project

        There is two kind of activation mode for a criterion:
         * department_centroid : the criteria is activated if the department centroid is in the activation map
         * hedges_intersection : the criteria is activated if the activation map intersects with the hedges to remove
        """
        dept_centroid = self.department.centroid
        hedges = self.catalog["haies"].hedges() if "haies" in self.catalog else []

        # Filter for department_centroid activation mode
        subquery = Zone.objects.filter(
            map_id=OuterRef("activation_map_id"), geometry__intersects=dept_centroid
        ).values("id")
        department_centroid_criteria = (
            super()
            .get_criteria()
            .filter(
                Exists(subquery),
                activation_mode="department_centroid",
            )
        )

        # Filter for hedges_intersection activation mode
        hedges_intersection_criteria = super().get_criteria().none()
        if hedges:
            zone_subquery = self.get_zone_subquery(hedges)
            hedges_intersection_criteria = (
                super()
                .get_criteria()
                .filter(Exists(zone_subquery), activation_mode="hedges_intersection")
            )

        return department_centroid_criteria | hedges_intersection_criteria

    def get_zone_subquery(self, hedges):
        query = Q()
        for hedge in hedges:
            query |= Q(geometry__intersects=hedge.geos_geometry)

        zone_subquery = Zone.objects.filter(
            Q(map_id=OuterRef("activation_map_id")) & query
        ).values("id")
        return zone_subquery

    def summary_fields(self):
        """Add fake fields to display pac related data."""
        fields = super().summary_fields()

        # add an entry in the project summary
        lineaire_detruit_pac = round(self.catalog.get("lineaire_detruit_pac", 0))
        localisation_pac = self.catalog.get("localisation_pac", False)

        if localisation_pac and lineaire_detruit_pac > 0:
            # Create a fake form to add a field in the "caractéristiques du projet" panel
            # It is a bit hacky but I cant find a better way to achieve this
            mock_form = Form(data={"lineaire_detruit_pac": str(lineaire_detruit_pac)})
            lineaire_detruit_pac = BoundField(
                form=mock_form,
                field=DisplayIntegerField(
                    label="Linéaire de haie pris en compte pour la conditionnalité PAC :",
                    display_help_text="Les alignements d’arbres sont exclus des règles de conditionnalité PAC.",
                    required=False,
                    min_value=0,
                    display_unit="m",
                ),
                name="lineaire_detruit_pac",
            )

            fields = insert_before(
                fields, "lineaire_detruit_pac", lineaire_detruit_pac, "lineaire_total"
            )

        return fields

    def get_regulations_by_group(self):
        """Group regulations by their result_group"""
        regulations_list = sorted(
            self.regulations, key=lambda regulation: regulation.display_order
        )

        regulations_list.sort(key=attrgetter("result_group"))
        grouped = {
            key: list(group)
            for key, group in groupby(regulations_list, key=attrgetter("result_group"))
        }
        return grouped

    def get_map_center(self):
        """Returns at what coordinates is the perimeter."""

        return self.department.centroid

    @property
    def requires_hedge_density(self):
        """Check if the moulinette requires the hedge density to be evaluated."""
        return any(
            isinstance(criterion._evaluator, HedgeDensityMixin)
            for regulation in self.regulations
            for criterion in regulation.criteria.all()
        )

    @cached_property
    def hedges_intersecting_regulations_perimeter(self):
        """Return for each regulation the hedges intersecting its perimeters.

        Return:
            dict: sets of hedges intersecting perimeters by type, by perimeter and by regulation
            {
            regulation:{
                    perimeter:{
                        hedge_type: sorted list of hedges
                    }
                }
            }
        """
        regulations_dd = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

        hedges = self.catalog["haies"].hedges() if "haies" in self.catalog else []
        if not hedges:
            return {}

        regulations = self.regulations

        perimeter_to_regulations = defaultdict(set)
        for regulation in regulations:
            for perimeter in regulation.perimeters.all():
                perimeter_to_regulations[perimeter].add(regulation)

        perimeter_zones = {
            perimeter: list(perimeter.activation_map.zones.all())
            for perimeter in perimeter_to_regulations
        }

        for hedge in hedges:
            hedge_geom = hedge.geos_geometry

            for perimeter, zones in perimeter_zones.items():
                if not any(zone.geometry.intersects(hedge_geom) for zone in zones):
                    continue

                for regulation in perimeter_to_regulations[perimeter]:
                    regulations_dd[regulation][perimeter][hedge.type].add(hedge)

        return {
            regulation: {
                perimeter: {
                    hedge_type: sorted(hedges, key=lambda h: h.id)
                    for hedge_type, hedges in by_type.items()
                }
                for perimeter, by_type in perimeters.items()
            }
            for regulation, perimeters in regulations_dd.items()
        }


class ActionToTake(models.Model):
    """Actions to take listed in an evaluation and debug page

    Actions to take are displayed in an evaluation if:
    - ACTIONS_TO_TAKE_MATRIX is set in a related Regulation or Criterion evaluator class
    - Display actions to take is True in Evaluation object
    """

    slug = models.CharField(
        "Référence de l'action",
        max_length=50,
        choices=ACTIONS_TO_TAKE,
        unique=True,
    )
    type = models.CharField(
        "Type d'action",
        max_length=20,
        choices=Choices(
            ("action", "Action"),
            ("pc", "Pièce complémentaire"),
        ),
    )
    target = models.CharField("Cible", max_length=20, choices=USER_TYPES)
    order = models.PositiveIntegerField("Ordre", default=1)

    label = models.TextField(
        verbose_name="Titre affiché",
        help_text="Texte de niveau 1",
    )
    details = models.CharField(
        verbose_name="Détails",
        max_length=255,
        help_text="Texte de niveau 2, choisir le template correspondant.",
    )

    documents_to_attach = ArrayField(
        models.CharField(max_length=255),
        verbose_name="référence des pièces complémentaires",
        help_text="Valeurs séparées par des virgules sans espace",
        blank=True,
        default=list,
    )

    def __str__(self):
        return self.get_slug_display()

    class Meta:
        verbose_name = "Action à mener"
        verbose_name_plural = "Actions à mener"
        ordering = ["order"]
