from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import TYPE_CHECKING, Literal

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeData
from envergo.moulinette.models import GLOBAL_RESULT_MATRIX

if TYPE_CHECKING:
    from envergo.moulinette.models import MoulinetteHaie


class PlantationResults(Enum):
    Adequate = "adequate"
    Inadequate = "inadequate"


PLANTATION_RESULT_MATRIX = {
    (RESULTS.interdit, PlantationResults.Inadequate.value): RESULTS.interdit,
    (RESULTS.interdit, PlantationResults.Adequate.value): RESULTS.interdit,
    (
        RESULTS.soumis,
        PlantationResults.Inadequate.value,
    ): PlantationResults.Inadequate.value,
    (RESULTS.soumis, PlantationResults.Adequate.value): RESULTS.soumis,
    # not used for now
    (
        RESULTS.action_requise,
        PlantationResults.Inadequate.value,
    ): RESULTS.non_disponible,
    (RESULTS.action_requise, PlantationResults.Adequate.value): RESULTS.non_disponible,
    (RESULTS.non_soumis, PlantationResults.Inadequate.value): RESULTS.non_disponible,
    (RESULTS.non_soumis, PlantationResults.Adequate.value): RESULTS.non_disponible,
    (
        RESULTS.non_disponible,
        PlantationResults.Inadequate.value,
    ): RESULTS.non_disponible,
    (RESULTS.non_disponible, PlantationResults.Adequate.value): RESULTS.non_disponible,
}


def _check_plantation_result_matrix():
    all_global_results = [
        global_result for global_result in set(GLOBAL_RESULT_MATRIX.values())
    ]
    all_plantation_results = [p.value for p in PlantationResults]

    # Generate all possible combinations
    expected_combinations = set(product(all_global_results, all_plantation_results))

    # Get actual keys from the matrix
    existing_combinations = set(PLANTATION_RESULT_MATRIX.keys())

    # Find missing combinations
    missing_combinations = expected_combinations - existing_combinations

    # Raise an error if there are missing cases
    if missing_combinations:
        raise ValueError(
            f"Missing cases in PLANTATION_RESULT_MATRIX: {missing_combinations}"
        )


_check_plantation_result_matrix()


@dataclass
class EvaluationResult:
    result: Literal[PlantationResults.Adequate, PlantationResults.Inadequate]
    conditions: list[str]
    evaluation: dict


class PlantationEvaluator:
    """Evaluate the adequacy of a plantation project.

    The plantation evaluator is used to evaluate if a project is compliant with the regulation.
    """

    def __init__(self, moulinette: "MoulinetteHaie", hedge_data: HedgeData):
        self.moulinette = moulinette
        self.hedge_data = hedge_data
        self.evaluate()

    @property
    def result(self):
        """Return the evaluator result.

        This value is used to select the plantation result templates.
        """
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._evaluation_result.result.value

    @property
    def global_result(self):
        """Return the project result combining both removal and plantation.

        This value is used to select the plantation result templates.
        """
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return PLANTATION_RESULT_MATRIX.get(
            (self.moulinette.result, self.result), RESULTS.interdit
        )

    @property
    def result_code(self):
        """Return the plantation evaluator result code.

        The result code is a unique code used to render the criterion template.
        """
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return f"{self.moulinette.result}_{self.result}"

    @property
    def unfulfilled_conditions(self):
        """Return the list of conditions that are not met to make the plantation project adequate."""
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._evaluation_result.conditions

    @property
    def evaluation(self):
        """Return the list of conditions that are not met to make the plantation project adequate."""
        if not hasattr(self, "_evaluation_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._evaluation_result.evaluation

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""

        evaluator = HedgeEvaluator(self.hedge_data)
        evaluation = evaluator.result
        result = EvaluationResult(
            result=(
                PlantationResults.Adequate
                if all(evaluation[item]["result"] for item in evaluation.keys())
                else PlantationResults.Inadequate
            ),
            conditions=[
                item for item in evaluation.keys() if not evaluation[item]["result"]
            ],
            evaluation=evaluation,
        )

        self._evaluation_result = result
        return result


class HedgeEvaluator:
    """Evaluate the adequacy of a plantation project.

    The plantation evaluator is used to evaluate if a project is compliant with the regulation.
    """

    def __init__(self, hedge_data: HedgeData):
        self.hedge_data = hedge_data
        self.result = self.evaluate()

    def is_not_planting_under_power_line(self):
        """Returns True if there is NO hedges to plant, containing high-growing trees (type alignement or mixte),
        that are under power line"""
        return not any(
            h.hedge_type in ["alignement", "mixte"]
            and h.additionalData.get("sousLigneElectrique", False)
            for h in self.hedge_data.hedges_to_plant()
        )

    def is_length_to_plant_sufficient(self):
        """Returns True if the length of hedges to plant is sufficient

        LP : longueur totale plantée
        LD : longueur totale détruite
        R : coefficient de replantation exigée

        Condition à remplir :
        LP ≥ R x LD
        """
        return (
            self.hedge_data.length_to_plant()
            >= self.hedge_data.minimum_length_to_plant()
        )

    def evaluate_hedge_plantation_quality(self):
        """Evaluate the quality of the plantation project.
        The quality of the hedge planted must be at least as good as that of the hedge destroyed:
            Type 5 (mixte) hedges must be replaced by type 5 (mixte) hedges
            Type 4 (alignement) hedges must be replaced by type 4 (alignement) or 5 (mixte) hedges.
            Type 3 (arbustive) hedges must be replaced by type 3 (arbustive) hedges.
            Type 2 (buissonnante) hedges must be replaced by type 2 (buissonnante) or 3 (arbustive) hedges.
            Type 1 (degradee) hedges must be replaced by type 2 (buissonnante), 3 (arbustive) or 5 (mixte) hedges.

        return: {
            is_quality_sufficient: True if the plantation quality is sufficient, False otherwise,
            missing_plantation: {
                mixte: missing length of mixte hedges to plant,
                alignement: missing length of alignement hedges to plant,
                arbustive: missing length of arbustive hedges to plant,
                buissonante: missing length of buissonante hedges to plant,
                degradee: missing length of dégradée hedges to plant,
            }
        }
        """
        minimum_lengths_to_plant = self.hedge_data.get_minimum_lengths_to_plant()
        lengths_to_plant = self.hedge_data.get_lengths_to_plant()

        reliquat = {
            "mixte_remplacement_alignement": max(
                0, lengths_to_plant["mixte"] - minimum_lengths_to_plant["mixte"]
            ),
            "mixte_remplacement_dégradée": max(
                0,
                max(0, lengths_to_plant["mixte"] - minimum_lengths_to_plant["mixte"])
                - max(
                    0,
                    minimum_lengths_to_plant["alignement"]
                    - lengths_to_plant["alignement"],
                ),
            ),
            "arbustive_remplacement_buissonnante": max(
                0, lengths_to_plant["arbustive"] - minimum_lengths_to_plant["arbustive"]
            ),
            "arbustive_remplacement_dégradée": max(
                0,
                max(
                    0,
                    lengths_to_plant["arbustive"]
                    - minimum_lengths_to_plant["arbustive"],
                )
                - max(
                    0,
                    minimum_lengths_to_plant["buissonnante"]
                    - lengths_to_plant["buissonnante"],
                ),
            ),
            "buissonnante_remplacement_dégradée": max(
                0,
                lengths_to_plant["buissonnante"]
                - minimum_lengths_to_plant["buissonnante"],
            ),
        }

        missing_plantation = {
            "mixte": max(
                0, minimum_lengths_to_plant["mixte"] - lengths_to_plant["mixte"]
            ),
            "alignement": max(
                0,
                minimum_lengths_to_plant["alignement"]
                - lengths_to_plant["alignement"]
                - reliquat["mixte_remplacement_alignement"],
            ),
            "arbustive": max(
                0, minimum_lengths_to_plant["arbustive"] - lengths_to_plant["arbustive"]
            ),
            "buissonante": max(
                0,
                minimum_lengths_to_plant["buissonnante"]
                - lengths_to_plant["buissonnante"]
                - reliquat["arbustive_remplacement_buissonnante"],
            ),
            "degradee": max(
                0,
                minimum_lengths_to_plant["degradee"]
                - reliquat["mixte_remplacement_dégradée"]
                - reliquat["arbustive_remplacement_dégradée"]
                - reliquat["buissonnante_remplacement_dégradée"],
            ),
        }

        return {
            "result": all(
                [
                    missing_plantation["mixte"] == 0,
                    missing_plantation["alignement"] == 0,
                    missing_plantation["arbustive"] == 0,
                    missing_plantation["buissonante"] == 0,
                    missing_plantation["degradee"] == 0,
                ]
            ),
            "missing_plantation": missing_plantation,
        }

    def evaluate_length_to_plant(self):
        """Evaluate if there is enough hedges to plant in the project"""
        left_to_plant = max(
            0,
            self.hedge_data.minimum_length_to_plant()
            - self.hedge_data.length_to_plant(),
        )
        return {
            "result": self.is_length_to_plant_sufficient(),
            "minimum_length_to_plant": self.hedge_data.minimum_length_to_plant(),
            "left_to_plant": left_to_plant,
        }

    def evaluate_length_to_plant_pac(self):
        """Evaluate if there is enough hedges to plant in PAC parcel in the project"""
        minimum_length_to_plant = (
            self.hedge_data.lineaire_detruit_pac()
        )  # no R coefficient for PAC
        left_to_plant = max(
            0,
            minimum_length_to_plant - self.hedge_data.length_to_plant_pac(),
        )
        return {
            "result": left_to_plant == 0,
            "minimum_length_to_plant": minimum_length_to_plant,
            "left_to_plant": left_to_plant,
        }

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""
        return {
            "length_to_plant": self.evaluate_length_to_plant(),
            "length_to_plant_pac": self.evaluate_length_to_plant_pac(),
            "quality": self.evaluate_hedge_plantation_quality(),
            "do_not_plant_under_power_line": {
                "result": self.is_not_planting_under_power_line(),
            },
        }
