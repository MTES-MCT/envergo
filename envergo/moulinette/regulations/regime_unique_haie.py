from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import PlantationConditionMixin
from envergo.moulinette.regulations import (
    HaieCriterionCategory,
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
    HedgeDensityMixin,
)


def compute_ru_compensation_ratio(moulinette):
    """Compute the régime unique compensation ratio.

    Returns the weighted average of per-hedge-type compensation coefficients
    (from the department config), weighted by hedge length. Alignements are
    excluded. Returns 0.0 when the department is not in régime unique.
    """
    if not moulinette.config.single_procedure:
        return 0.0

    haies = moulinette.catalog["haies"]
    total_length = haies.length_to_remove()
    if total_length == 0:
        return 0.0

    coeff_by_type = moulinette.config.single_procedure_settings["coeff_compensation"]

    compensated_length = 0.0
    for hedge in haies.hedges_to_remove().n_alignement():
        compensated_length += hedge.length * coeff_by_type[hedge.hedge_type]

    return round(compensated_length / total_length, 2)


class RegimeUniqueHaieRegulation(HaieRegulationEvaluator):
    """Regulation-level evaluator for the régime unique haie procedure."""

    choice_label = "Haie > Régime unique"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
    }


class RegimeUniqueHaieHru(HaieCriterionEvaluator):
    """Criterion evaluator for the régime unique haie procedure.

    Determines whether a hedge project falls under the régime unique
    (single procedure) or droit constant, and whether it is soumis or
    non concerné based on hedge types.
    """

    choice_label = "Régime unique haie > Régime unique haie"
    slug = "regime_unique_haie"
    category = HaieCriterionCategory.hru

    RESULT_MATRIX = {
        "non_concerne": RESULTS.non_concerne,
        "non_active": RESULTS.non_active,
    }

    CODE_MATRIX = {
        "regime_unique": "non_concerne",
        "droit_constant": "non_active",
    }

    def get_result_data(self):
        regime_unique = self.moulinette.config.single_procedure
        return "regime_unique" if regime_unique else "droit_constant"


class RegimeUniqueHaieRu(
    PlantationConditionMixin, HedgeDensityMixin, RegimeUniqueHaieHru
):
    """Criterion evaluator for the régime unique haie procedure.

    Determines whether a hedge project falls under the régime unique
    (single procedure) or droit constant, and whether it is soumis or
    non concerné based on hedge types.
    """

    plantation_conditions = []
    category = HaieCriterionCategory.ru

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"

    def get_catalog_data(self):
        """Inject 400m line-buffer density into the catalog when in régime unique."""
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies and self.moulinette.config.single_procedure:
            density_data = haies.density_around_lines
            catalog["density_400"] = density_data.get("density_400")
            catalog["density_400_length"] = density_data.get("length_400")
            catalog["density_400_area_ha"] = density_data.get("area_400_ha")
        return catalog

    def get_replantation_coefficient(self):
        """Return the RU compensation ratio for replantation requirements."""
        return compute_ru_compensation_ratio(self.moulinette)


class RegimeUniqueHaieL3503(RegimeUniqueHaieHru):
    """Criterion evaluator for the régime unique haie procedure.

    Determines whether a hedge project falls under the régime unique
    (single procedure) or droit constant, and whether it is soumis or
    non concerné based on hedge types.
    """

    category = HaieCriterionCategory.l350_3

    def evaluate(self):
        self._result_code, self._result = "non_concerne", "non_concerne"
