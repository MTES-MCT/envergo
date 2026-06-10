"""Régime unique haie — criterion evaluator.

Determines whether a hedge project falls under the régime unique
(single procedure) and whether it is soumis or non concerné.
"""

from django import forms

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import (
    PlantationConditionMixin,
    RUMinLengthCondition,
    RUQualityCondition,
    SafetyCondition,
)
from envergo.moulinette.regulations import (
    CriterionEvaluator,
    HaieRegulationEvaluator,
    HedgeDensityMixin,
)
from envergo.moulinette.regulations.regime_unique import (
    compute_ru_compensation_ratio,
    get_ru_debug_context,
    get_ru_per_hedge_coefficients,
    get_ru_zone_data,
)

URGENCE_MOTIFS = ("securite", "chemin_acces", "autre")


class RegimeUniqueHaieForm(forms.Form):
    """Complementary question about emergency works.

    Shown only when the motif suggests a possible emergency situation
    and the department is under the régime unique.
    """

    urgence = forms.ChoiceField(
        label="Les travaux sont-ils réalisés en urgence ?",
        widget=forms.RadioSelect,
        choices=(
            ("non", "Non, les travaux ne sont pas réalisés en urgence."),
            (
                "oui",
                "Oui, les travaux sont réalisés en urgence et ont déjà été "
                "exécutés, ou le seront dans les prochains jours.",
            ),
        ),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.data if self.data else self.initial
        motif = data.get("motif")
        if motif not in URGENCE_MOTIFS:
            self.fields = {}


class RegimeUniqueHaieRegulation(HaieRegulationEvaluator):
    """Regulation-level evaluator for the régime unique haie procedure."""

    choice_label = "Haie > Régime unique"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
    }


class RegimeUniqueHaie(PlantationConditionMixin, HedgeDensityMixin, CriterionEvaluator):
    """Criterion evaluator for the régime unique haie procedure.

    Determines whether a hedge project falls under the régime unique
    (single procedure) or droit constant, and whether it is soumis or
    non concerné based on hedge types.
    """

    choice_label = "Régime unique haie > Régime unique haie"
    slug = "regime_unique_haie"
    form_class = RegimeUniqueHaieForm
    plantation_conditions = [RUMinLengthCondition, RUQualityCondition, SafetyCondition]

    RESULT_MATRIX = {
        "non_disponible": RESULTS.non_disponible,
        "non_concerne": RESULTS.non_concerne,
        "non_concerne_aa": RESULTS.non_concerne,
        "soumis": RESULTS.soumis,
    }

    CODE_MATRIX = {
        ("regime_unique", "aa_only"): "non_concerne_aa",
        ("regime_unique", "has_hedges"): "soumis",
        ("droit_constant", "aa_only"): "non_concerne",
        ("droit_constant", "has_hedges"): "non_concerne",
    }

    def get_form_class(self):
        """Only expose the emergency form when single_procedure is active."""
        if not self.moulinette.config.single_procedure:
            return None
        return self.form_class

    def get_form(self):
        """Gate form instantiation on single_procedure."""
        if not self.moulinette.config.single_procedure:
            return None
        return super().get_form()

    def get_result_code(self, result_data):
        """Override to detect missing zone config before the CODE_MATRIX lookup."""
        if self.moulinette.config.single_procedure and not self.catalog.get(
            "ru_all_zones_resolved", False
        ):
            return "non_disponible"
        return super().get_result_code(result_data)

    def get_catalog_data(self):
        """Inject density and zone-based coefficient data when in régime unique."""
        catalog = super().get_catalog_data()
        if self.moulinette.config.single_procedure:
            catalog.update(self.get_density_catalog_data())
            if "per_hedge_coefficients" not in self.catalog:
                zone_data = get_ru_zone_data(self.moulinette)
                catalog.update(zone_data)
                zone_configs = zone_data["ru_per_hedge_zone_configs"]
                catalog.update(
                    get_ru_per_hedge_coefficients(self.moulinette, zone_configs)
                )
        return catalog

    def get_result_data(self):
        """Return a (procedure_mode, hedge_presence) tuple for CODE_MATRIX lookup."""
        hedges = self.catalog["haies"].hedges_to_remove()
        has_hedges = any(h for h in hedges if h.hedge_type != "alignement")
        regime_unique = self.moulinette.config.single_procedure

        procedure_mode = "regime_unique" if regime_unique else "droit_constant"
        hedge_presence = "has_hedges" if has_hedges else "aa_only"
        return procedure_mode, hedge_presence

    def get_debug_context(self):
        """Return density and per-hedge zone data for the debug template."""
        context = super().get_debug_context()
        context.update(get_ru_debug_context(self.catalog))
        return context

    @property
    def effective_coefficients(self):
        """Raw per-hedge zone-based compensation coefficients."""
        return self.catalog.get("per_hedge_coefficients", {})

    def get_replantation_coefficient(self):
        """Return the RU compensation ratio for replantation requirements."""
        return compute_ru_compensation_ratio(self.moulinette)
