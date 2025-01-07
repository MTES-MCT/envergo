from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal

import requests
from django.conf import settings

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
        url = f"{settings.PUBLICODES_SERVICE_URL}hedges/quality/"
        headers = {"Content-Type": "application/json"}
        data = {
            "minimum_lengths_to_plant": self.hedge_data.get_minimum_lengths_to_plant(),
            "lengths_to_plant": self.hedge_data.get_lengths_to_plant(),
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def evaluate(self):
        """Returns if the plantation is compliant with the regulation"""
        quality_evaluation = self.evaluate_hedge_plantation_quality()

        conditions = {
            "length_to_plant": self.is_length_to_plant_sufficient(),
            "quality": quality_evaluation["is_quality_sufficient"],
            "do_not_plant_under_power_line": self.is_not_planting_under_power_line(),
        }
        result = EvaluationResult(
            result=(
                PlantationResults.Adequate
                if all(conditions.values())
                else PlantationResults.Inadequate
            ),
            conditions=[
                condition for condition in conditions if not conditions[condition]
            ],
        )

        self._evaluation_result = result
        return result
