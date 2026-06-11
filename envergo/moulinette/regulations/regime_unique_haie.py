"""Régime unique haie — criterion evaluator.

Determines whether a hedge project falls under the régime unique
(single procedure) and whether it is soumis or non concerné.
"""

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
