"""Régime unique haie — criterion evaluator.

Determines whether a hedge project falls under the régime unique
(single procedure) and whether it is soumis or non concerné.
"""

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import (
    MinLengthCondition,
    PlantationConditionMixin,
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
    plantation_conditions = [MinLengthCondition, RUQualityCondition, SafetyCondition]

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

    def get_replantation_coefficient(self):
        """Return the RU compensation ratio for replantation requirements."""
        return compute_ru_compensation_ratio(self.moulinette)
