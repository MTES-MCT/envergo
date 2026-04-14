from collections import defaultdict

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import PlantationConditionMixin
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieCriterionScope,
    HaieRegulationEvaluator,
)


class RegimeUniqueHaieRegulation(HaieRegulationEvaluator):
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
    scope = HaieCriterionScope.hru

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


class RegimeUniqueHaieRu(PlantationConditionMixin, RegimeUniqueHaieHru):
    """Criterion evaluator for the régime unique haie procedure.

    Determines whether a hedge project falls under the régime unique
    (single procedure) or droit constant, and whether it is soumis or
    non concerné based on hedge types.
    """

    plantation_conditions = []
    scope = HaieCriterionScope.ru

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"

    def get_replantation_coefficient(self):
        if not self.moulinette.config.single_procedure:
            return 0.0

        haies = self.catalog["haies"]
        minimum_length_to_plant = 0.0
        lengths_by_type = defaultdict(int)
        for to_remove in haies.hedges_to_remove().ru():
            lengths_by_type[to_remove.hedge_type] += to_remove.length

        for hedge_type, length in lengths_by_type.items():
            coeff = self.moulinette.config.single_procedure_settings[
                "coeff_compensation"
            ][hedge_type]
            minimum_length_to_plant += length * coeff

        R = minimum_length_to_plant / haies.length_to_remove()
        return round(R, 2)


class RegimeUniqueHaieL3503(RegimeUniqueHaieHru):
    """Criterion evaluator for the régime unique haie procedure.

    Determines whether a hedge project falls under the régime unique
    (single procedure) or droit constant, and whether it is soumis or
    non concerné based on hedge types.
    """

    scope = HaieCriterionScope.l350_3

    def evaluate(self):
        self._result_code, self._result = "non_concerne", "non_concerne"
