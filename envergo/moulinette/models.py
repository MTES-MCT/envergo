import logging
from abc import ABC, abstractmethod
from collections import OrderedDict

from django.conf import settings
from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance as D
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Case, F, IntegerField, Prefetch, Q
from django.db.models import Value as V
from django.db.models import When
from django.db.models.functions import Cast, Concat
from django.http import QueryDict
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from model_utils import Choices
from phonenumber_field.modelfields import PhoneNumberField

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import Department, Zone
from envergo.moulinette.fields import CriterionEvaluatorChoiceField
from envergo.moulinette.forms import (
    MoulinetteFormAmenagement,
    MoulinetteFormHaie,
    TriageFormHaie,
)
from envergo.moulinette.regulations import Map, MapPolygon
from envergo.moulinette.utils import list_moulinette_templates
from envergo.utils.urls import update_qs

# WGS84, geodetic coordinates, units in degrees
# Good for storing data and working wordwide
EPSG_WGS84 = 4326

# Projected coordinates
# Used for displaying tiles in web map systems (OSM, GoogleMaps)
# Good for working in meters
EPSG_MERCATOR = 3857


logger = logging.getLogger(__name__)

HAIE_REGULATIONS = ["conditionnalite_pac", "dep"]

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
    ("conditionnalite_pac", "Conditionnalité PAC"),
    ("dep", "Dérogation « espèces protégées »"),
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

    @property
    def slug(self):
        return self.regulation

    @property
    def title(self):
        return self.get_regulation_display()

    @property
    def subtitle(self):
        subtitle_property = f"{self.regulation}_subtitle"
        sub = getattr(self, subtitle_property, None)
        return sub

    @property
    def eval_env_subtitle(self):
        """Custom subtitle for EvalEnv.

        When an Eval Env evaluation is "non soumis", we need to display that not
        all "rubriques" have been evaluated.
        """
        if self.result != "non_soumis":
            return None

        optional_criteria = [
            c
            for c in self.criteria.all()
            if c.is_optional and c.result != "non_disponible"
        ]
        subtitle = "(rubrique 39)" if not optional_criteria else None
        return subtitle

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
            all_perimeters = self.perimeters.all()
            activated_perimeters = [p for p in all_perimeters if p.is_activated]
            if all_perimeters and not any(activated_perimeters):
                return RESULTS.non_disponible
            if not all_perimeters:
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
            RESULTS.iota_a_verifier,
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
    def map(self):
        """Returns a map to be displayed for the regulation.

        Returns a `envergo.moulinette.regulations.Map` object or None.
        This map object will be serialized to Json and passed to a Leaflet
        configuration script.
        """

        # We use visually distinctive color palette to display perimeters.
        # https://d3js.org/d3-scale-chromatic/categorical#schemeTableau10
        palette = [
            self.polygon_color,
            "#4e79a7",
            "#e15759",
            "#76b7b2",
            "#59a14f",
            "#edc949",
            "#af7aa1",
            "#ff9da7",
            "#9c755f",
            "#bab0ab",
        ]
        perimeters = self.perimeters.all()
        if perimeters:
            polygons = [
                MapPolygon(
                    [perimeter], palette[counter % len(palette)], perimeter.map_legend
                )
                for counter, perimeter in enumerate(perimeters)
            ]
            map = Map(
                type="regulation",
                center=self.moulinette.catalog["coords"],
                entries=polygons,
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

    def has_several_perimeters(self):
        return len(self.perimeters.all()) > 1


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
    evaluator = CriterionEvaluatorChoiceField(_("Evaluator"))
    evaluator_settings = models.JSONField(
        _("Evaluator settings"), default=dict, blank=True
    )
    is_optional = models.BooleanField(
        _("Is optional"),
        default=False,
        help_text=_("Only show this criterion to admin users"),
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

    class Meta:
        verbose_name = _("Criterion")
        verbose_name_plural = _("Criteria")

    def __str__(self):
        return self.title

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


class ConfigBase(models.Model):
    department = models.OneToOneField(
        "geodata.Department",
        verbose_name=_("Department"),
        on_delete=models.PROTECT,
        related_name="%(class)s",
    )
    is_activated = models.BooleanField(
        _("Is activated"),
        help_text=_("Is the moulinette available for this department?"),
        default=False,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.department.get_department_display()


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
    criteria_values = models.JSONField(
        "Valeurs des critères", default=dict, null=False, blank=True
    )

    class Meta:
        verbose_name = _("Config amenagement")
        verbose_name_plural = _("Configs amenagement")


class ConfigHaie(ConfigBase):
    """Some moulinette content depends on the department.

    This object is dedicated to the Haie moulinette. For Amenagement, see ConfigAmenagement.
    """

    regulations_available = HAIE_REGULATIONS

    department_guichet_unique_url = models.URLField(
        "Url du guichet unique de la haie du département (si existant)", blank=True
    )

    contacts_and_links = models.TextField(
        "Liste des contacts et liens utiles", blank=True
    )

    def __str__(self):
        return self.department.get_department_display()

    class Meta:
        verbose_name = "Config haie"
        verbose_name_plural = "Configs haie"


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

    REGULATIONS = [
        "loi_sur_leau",
        "natura2000",
        "eval_env",
        "sage",
        "conditionnalite_pac",
        "dep",
    ]

    def __init__(self, data, raw_data, activate_optional_criteria=True):
        if isinstance(raw_data, QueryDict):
            self.raw_data = raw_data.dict()
        else:
            self.raw_data = raw_data
        self.catalog = MoulinetteCatalog(**data)
        self.catalog.update(self.get_catalog_data())

        # Some criteria must be hidden to normal users in the
        self.activate_optional_criteria = activate_optional_criteria

        self.department = self.get_department()

        self.config = self.catalog["config"] = self.get_config()
        if self.config and self.config.id and hasattr(self.config, "templates"):
            self.templates = {t.key: t for t in self.config.templates.all()}
        else:
            self.templates = {}

        self.evaluate()

    @property
    def regulations(self):
        if not hasattr(self, "_regulations"):
            self._regulations = self.get_regulations()
        return self._regulations

    @regulations.setter
    def regulations(self, value):
        self._regulations = value

    def evaluate(self):
        for regulation in self.regulations:
            regulation.evaluate(self)

    def has_config(self):
        return bool(self.config)

    @abstractmethod
    def get_config(self):
        pass

    def get_template(self, template_key):
        """Return the MoulinetteTemplate with the given key."""

        return self.templates.get(template_key, None)

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

    @classmethod
    def get_main_form_class(cls):
        """Return the form class for the main questions."""

        if not hasattr(cls, "main_form_class"):
            raise AttributeError("No main form class found.")
        return cls.main_form_class

    def get_criteria(self):
        """Fetch relevant criteria for evaluation.

        We don't actually use the criteria directly, the returned queryset will only
        be used in a prefetch_related call when we fetch the regulations.
        """
        criteria = (
            Criterion.objects.order_by("weight")
            .distinct("weight", "id")
            .prefetch_related("templates")
            .annotate(distance=Cast(0, IntegerField()))
        )

        # We might have to filter out optional criteria
        if not self.activate_optional_criteria:
            criteria = criteria.exclude(is_optional=True)

        return criteria

    @classmethod
    def get_optionnal_criteria(self):
        """Fetch optionnal criteria used by this moulinette regulations."""
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
        return {}

    def is_evaluation_available(self):
        return self.config and self.config.is_activated

    def has_missing_data(self):
        """Make sure all the data required to compute the result is provided."""

        form_errors = []
        for regulation in self.regulations:
            for criterion in regulation.criteria.all():
                form = criterion.get_form()
                # We check for each form for errors
                if form:
                    form.full_clean()

                    # For optional forms, we only check for errors if the form
                    # was activated (the "activate" checkbox was selected)
                    if (
                        criterion.is_optional
                        and self.activate_optional_criteria
                        and form.is_activated()
                    ):
                        form_errors.append(not form.is_valid())
                    elif not criterion.is_optional:
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
        """Returns the corresponding regulation.

        Allows to do something like this:
        moulinette.loi_sur_leau to fetch the correct regulation.
        """
        if attr in self.REGULATIONS:
            return self.get_regulation(attr)
        else:
            return super().__getattr__(attr)

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

        Some criteria need more data to return an answer. Here, we gather all
        the forms to gather this data.
        """

        forms = []

        for regulation in self.regulations:
            for criterion in regulation.criteria.all():
                if not criterion.is_optional:
                    form_class = criterion.get_form_class()
                    if form_class and form_class not in forms:
                        forms.append(form_class)

        return forms

    def main_form(self):
        """Get the instanciated main form questions."""

        form_class = self.get_main_form_class()
        return form_class(self.raw_data)

    def additional_forms(self):
        """Get a list of instanciated additional questions forms."""

        form_classes = self.additional_form_classes()
        forms = []
        for form_class in form_classes:
            form = form_class(self.raw_data)

            # Some forms end up with no fields, depending on the project data
            # so we just skip them
            if form.fields:
                forms.append(form)
        return forms

    def additional_fields(self):
        """Get a {field_name: field} dict of all additional questions fields."""

        forms = self.additional_forms()
        fields = OrderedDict()
        for form in forms:
            for field in form:
                if field.name not in fields:
                    fields[field.name] = field
        return fields

    def optional_form_classes(self):
        """Return the list of forms for optional questions."""
        forms = []

        for regulation in self.regulations:
            for criterion in regulation.criteria.all():
                if criterion.is_optional:
                    form_class = criterion.get_form_class()
                    if form_class and form_class not in forms:
                        forms.append(form_class)

        return forms

    def optional_forms(self):
        form_classes = self.optional_form_classes()
        forms = []
        for form_class in form_classes:
            form = form_class(self.raw_data)
            if form.fields:
                forms.append(form)
        return forms

    @abstractmethod
    def summary(self):
        """Build a data summary, for analytics purpose."""
        raise NotImplementedError

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
            ((RESULTS.non_soumis,), RESULTS.non_soumis),
            ((RESULTS.non_disponible,), RESULTS.non_disponible),
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

    @classmethod
    def get_form_template(cls):
        """Return the template name for the moulinette."""

        if not hasattr(cls, "form_template"):
            raise AttributeError("No form template name found.")
        return cls.form_template

    @abstractmethod
    def get_debug_context(self):
        """Add some data to display on the debug page"""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def get_triage_params(cls):
        """Add some data to display on the debug page"""
        raise NotImplementedError

    @classmethod
    def get_extra_context(cls, request):
        """return extra context data for the moulinette views.
        You can use this method to add some context specific to your site : Haie or Amenagement
        """

        return {}


class MoulinetteAmenagement(Moulinette):
    REGULATIONS = ["loi_sur_leau", "natura2000", "eval_env", "sage"]
    result_template = "amenagement/moulinette/result.html"
    debug_result_template = "amenagement/moulinette/result_debug.html"
    result_available_soon = "amenagement/moulinette/result_available_soon.html"
    result_non_disponible = "amenagement/moulinette/result_non_disponible.html"
    form_template = "amenagement/moulinette/form.html"
    main_form_class = MoulinetteFormAmenagement

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
            .annotate(distance=Cast(Distance("geometry", coords), IntegerField()))
            .order_by("id")
            .distinct("id")
            .select_related("activation_map")
            .defer("activation_map__geometry")
        )

        return perimeters

    def get_criteria(self):
        coords = self.catalog["coords"]

        criteria = (
            super()
            .get_criteria()
            .filter(
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
            .annotate(distance=Cast(Distance("geometry", coords), IntegerField()))
            .select_related("activation_map")
            .defer("activation_map__geometry")
        )

        return criteria

    def get_catalog_data(self):
        """Fetch / compute data required for further computations."""

        catalog = super().get_catalog_data()

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

        return summary

    def get_department(self):
        lng_lat = self.catalog["lng_lat"]
        department = (
            Department.objects.filter(geometry__contains=lng_lat)
            .select_related("configamenagement")
            .prefetch_related("configamenagement__templates")
            .first()
        )
        return department

    def get_config(self):
        return getattr(self.department, "configamenagement", None)

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

    @classmethod
    def get_triage_params(cls):
        return set()


class MoulinetteHaie(Moulinette):
    REGULATIONS = HAIE_REGULATIONS
    result_template = "haie/moulinette/result.html"
    debug_result_template = "haie/moulinette/result.html"
    result_available_soon = "haie/moulinette/result_non_disponible.html"
    result_non_disponible = "haie/moulinette/result_non_disponible.html"
    form_template = "haie/moulinette/form.html"
    main_form_class = MoulinetteFormHaie

    def get_config(self):
        return getattr(self.department, "confighaie", None)

    def summary(self):
        """Build a data summary, for analytics purpose."""
        # TODO
        summary = {
            "haie": "this is a haie simulation",
        }
        summary.update(self.cleaned_additional_data())

        if self.is_evaluation_available():
            summary["result"] = self.result_data()

        return summary

    def get_debug_context(self):
        return {}

    @classmethod
    def get_triage_params(cls):
        return set(TriageFormHaie.base_fields.keys())

    @classmethod
    def get_extra_context(cls, request):
        """return extra context data for the moulinette views.
        You can use this method to add some context specific to your site : Haie or Amenagement
        """
        context = {}
        form_data = request.GET
        context["triage_url"] = update_qs(reverse("triage"), form_data)

        context["demarche_url"] = settings.DEMARCHES_SIMPLIFIEE_HAIE_URL

        triage_form = TriageFormHaie(data=form_data)
        if triage_form.is_valid():
            context["triage_form"] = triage_form
        else:
            context["redirect_url"] = context["triage_url"]

        department_code = request.GET.get("department", None)
        department = (
            (
                Department.objects.defer("geometry")
                .filter(confighaie__is_activated=True, department=department_code)
                .first()
            )
            if department_code
            else None
        )
        context["department"] = department

        return context

    def get_department(self):
        department_code = self.raw_data.get("department", None)
        department = (
            (
                Department.objects.defer("geometry")
                .select_related("confighaie")
                .filter(department=department_code)
                .first()
            )
            if department_code
            else None
        )

        return department


def get_moulinette_class_from_site(site):
    """Return the correct Moulinette class depending on the current site."""

    domain_class = {
        settings.ENVERGO_AMENAGEMENT_DOMAIN: MoulinetteAmenagement,
        settings.ENVERGO_HAIE_DOMAIN: MoulinetteHaie,
    }
    cls = domain_class.get(site.domain, None)
    if cls is None:
        raise RuntimeError(f"Unknown site for domain {site.domain}")
    return cls


def get_moulinette_class_from_url(url):
    """Return the correct Moulinette class depending on the current site."""

    if "envergo" in url:
        cls = MoulinetteAmenagement
    elif "haie" in url:
        cls = MoulinetteHaie
    else:
        raise RuntimeError("Cannot find the moulinette to use")
    return cls
