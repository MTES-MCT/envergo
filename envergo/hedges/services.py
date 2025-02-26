from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeData

if TYPE_CHECKING:
    from envergo.moulinette.models import MoulinetteHaie


class PlantationResults(Enum):
    Adequate = "adequate"
    Inadequate = "inadequate"


@dataclass
class EvaluationResult:
    result: Literal[PlantationResults.Adequate, PlantationResults.Inadequate]
    conditions: list[str]


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

        result_matrix = {
            (RESULTS.interdit, PlantationResults.Inadequate.value): RESULTS.interdit,
            (RESULTS.interdit, PlantationResults.Adequate.value): RESULTS.interdit,
            (
                RESULTS.soumis,
                PlantationResults.Inadequate.value,
            ): PlantationResults.Inadequate.value,
            (RESULTS.soumis, PlantationResults.Adequate.value): RESULTS.soumis,
        }

        return result_matrix.get(
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

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""

        evaluator = HedgeEvaluator(self.hedge_data)
        evaluation = evaluator.evaluate()
        result = EvaluationResult(
            result=(
                PlantationResults.Adequate
                if all(evaluation[item]["result"] for item in evaluation.keys())
                else PlantationResults.Inadequate
            ),
            conditions=[
                item for item in evaluation.keys() if not evaluation[item]["result"]
            ],
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

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""
        return {
            "length_to_plant": {
                "result": self.is_length_to_plant_sufficient(),
                "minimum_length_to_plant": self.hedge_data.minimum_length_to_plant(),
                "left_to_plant": (
                    self.hedge_data.minimum_length_to_plant()
                    - self.hedge_data.length_to_plant()
                    if self.hedge_data.minimum_length_to_plant()
                    > self.hedge_data.length_to_plant()
                    else 0
                ),
            },
            "quality": self.evaluate_hedge_plantation_quality(),
            "do_not_plant_under_power_line": {
                "result": self.is_not_planting_under_power_line(),
            },
        }
