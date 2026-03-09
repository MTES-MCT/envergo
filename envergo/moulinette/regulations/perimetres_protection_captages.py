from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator


class PerimetresProtectionCaptagesRegulation(HaieRegulationEvaluator):
    """Evaluate the périmètres de protection de captages regulation."""

    choice_label = "Haie > Périmètres de protection de captages"

    PROCEDURE_TYPE_MATRIX = {
        "a_verifier": "declaration",
        "non_concerne": "declaration",
    }


class PerimetresProtectionCaptagesHaie(CriterionEvaluator):
    """Evaluate the périmètres de protection de captages criterion.

    Returns a_verifier if any hedge (to remove or to plant) intersects
    the activation map, non_concerne otherwise.
    """

    choice_label = (
        "Périmètres de protection de captages > Périmètres de protection de captages"
    )
    slug = "perimetres_protection_captages"
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
