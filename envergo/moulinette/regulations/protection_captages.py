from abc import ABC

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class ProtectionCaptagesRegulation(HaieRegulationEvaluator):
    """Evaluate the protection de captages regulation."""

    choice_label = "Haie > Protection de captages"

    PROCEDURE_TYPE_MATRIX = {
        "a_verifier": "declaration",
        "non_concerne": "declaration",
    }


class ProtectionCaptagesHaieBase(HaieCriterionEvaluator, ABC):
    """Evaluate the "protection de captages" criterion.

    Returns a_verifier if any hedge (to remove or to plant) intersects
    the activation map, non_concerne otherwise.
    """

    choice_label = "Protection de captages > Protection de captages"
    base_slug = "protection_captages"
    plantation_conditions = []

    RESULT_MATRIX = {
        "a_verifier": RESULTS.a_verifier,
        "non_concerne": RESULTS.non_concerne,
    }

    CODE_MATRIX = {
        True: "a_verifier",
        False: "non_concerne",
    }

    def get_result_data(self):
        """Check if any hedge (to remove or to plant) intersects the activation map.

        If this criterion is being evaluated, it was activated — meaning
        at least one hedge intersects the perimeter.
        """
        return True


class ProtectionCaptagesHaieHru(ProtectionCaptagesHaieBase):
    category = HedgeCategory.hru


class ProtectionCaptagesHaieRu(ProtectionCaptagesHaieBase):
    category = HedgeCategory.ru


class ProtectionCaptagesHaieL3503(ProtectionCaptagesHaieBase):
    category = HedgeCategory.l350_3
