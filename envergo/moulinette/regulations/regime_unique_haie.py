"""Régime unique haie — criterion evaluator.

Determines whether a hedge project falls under the régime unique
(single procedure) and whether it is soumis or non concerné.
"""

from django import forms

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeCategory
from envergo.hedges.regulations import (
    PlantationConditionMixin,
    RUMinLengthCondition,
    RUQualityCondition,
    SafetyCondition,
)
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
    HedgeDensityMixin,
)
from envergo.moulinette.regulations.regime_unique import (
    collect_zone_configs,
    compute_ru_compensation_ratio,
    ensure_ru_hedge_data,
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


class RegimeUniqueHaieRu(
    PlantationConditionMixin, HedgeDensityMixin, HaieCriterionEvaluator
):
    """Criterion evaluator for the régime unique haie procedure.

    Determines whether a hedge project falls under the régime unique
    (single procedure) or droit constant, and whether it is soumis or
    non concerné based on hedge types.
    """

    choice_label = "Régime unique haie > Régime unique haie"
    base_slug = "regime_unique_haie"
    form_class = RegimeUniqueHaieForm
    plantation_conditions = [RUMinLengthCondition, RUQualityCondition, SafetyCondition]
    category = HedgeCategory.ru

    RESULT_MATRIX = {
        "non_disponible": RESULTS.non_disponible,
        "non_concerne": RESULTS.non_concerne,
        "soumis": RESULTS.soumis,
    }

    CODE_MATRIX = {
        ("regime_unique", "ru_all_zones_resolved"): "soumis",
        ("regime_unique", "unresolved"): "non_disponible",
        ("droit_constant", "ru_all_zones_resolved"): "non_active",
        ("droit_constant", "unresolved"): "non_active",
    }

    def get_result_data(self):
        regime_unique = self.moulinette.config.single_procedure

        procedure_mode = "regime_unique" if regime_unique else "droit_constant"

        zones_resolved = (
            "ru_all_zones_resolved"
            if self.catalog.get("ru_all_zones_resolved", False)
            else "unresolved"
        )

        return procedure_mode, zones_resolved

    def get_form_class(self):
        """Only expose the emergency form when single_procedure is active."""
        if not self.moulinette.config.single_procedure:
            return None
        return self.form_class

    def get_catalog_data(self):
        """Inject density and zone-based coefficient data when in régime unique."""
        catalog = super().get_catalog_data()
        if self.moulinette.config.single_procedure:
            catalog.update(self.get_density_catalog_data())
            ensure_ru_hedge_data(self.moulinette, self.hedges)
        return catalog

    def get_debug_context(self):
        """Return density and zone config data for the debug template."""
        context = super().get_debug_context()
        context["ru_zone_configs"] = collect_zone_configs(
            self.catalog.get("ru_hedge_data", {})
        )
        return context

    @property
    def effective_coefficients(self):
        """Raw per-hedge zone-based compensation coefficients."""
        hedge_data = self.catalog.get("ru_hedge_data", {})
        return {h: rec["raw_coefficient"] for h, rec in hedge_data.items()}

    def get_replantation_coefficient(self):
        """Return the RU compensation ratio for replantation requirements."""
        if not self.moulinette.config.single_procedure:
            return 0.0
        hedges = self.hedges.to_remove().n_alignement()
        return compute_ru_compensation_ratio(hedges, self.effective_coefficients)
