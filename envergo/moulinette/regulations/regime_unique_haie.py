from collections import defaultdict

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import PlantationConditionMixin
from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator


class RegimeUniqueHaieRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Régime unique"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
    }


class RegimeUniqueHaie(PlantationConditionMixin, CriterionEvaluator):
    choice_label = "Régime unique haie > Régime unique haie"
    slug = "regime_unique_haie"
    plantation_conditions = []

    RESULT_MATRIX = {
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

    def get_result_data(self):
        hedges = self.catalog["haies"].hedges_to_remove()
        has_hedges = any(h for h in hedges if h.hedge_type != "alignement")
        regime_unique = self.moulinette.config.single_procedure

        return "regime_unique" if regime_unique else "droit_constant", (
            "aa_only" if not has_hedges else "has_hedges"
        )

    def get_replantation_coefficient(self):
        if not self.moulinette.config.single_procedure:
            return 0.0

        haies = self.catalog["haies"]
        minimum_length_to_plant = 0.0
        lengths_by_type = defaultdict(int)
        for to_remove in haies.hedges_to_remove():
            lengths_by_type[to_remove.hedge_type] += to_remove.length

        for hedge_type, length in lengths_by_type.items():
            if hedge_type == "alignement":
                continue

            coeff = self.moulinette.config.single_procedure_settings[
                "coeff_compensation"
            ][hedge_type]
            minimum_length_to_plant += length * coeff

        R = minimum_length_to_plant / haies.length_to_remove()
        return round(R, 2)
