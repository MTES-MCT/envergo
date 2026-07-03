from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class LoiSurLeauHaieRegulation(HaieRegulationEvaluator):
    """Evaluate the loi sur l'eau (haie) regulation."""

    choice_label = "Haie > Loi sur l'eau"

    PROCEDURE_TYPE_MATRIX = {
        "a_verifier": "declaration",
        "soumis": "declaration",
        "non_soumis": "declaration",
        "non_concerne": "declaration",
    }


class LoiSurLeauHaieHru(HaieCriterionEvaluator):
    """Evaluate the loi sur l'eau (haie) criterion."""

    choice_label = "Loi sur l'eau Haie > Loi sur l'eau Haie"
    base_slug = "loi_sur_leau_haie"
    plantation_conditions = []
    category = HedgeCategory.hru

    RESULT_MATRIX = {
        "a_verifier": RESULTS.a_verifier,
        "non_concerne": RESULTS.non_concerne,
    }

    CODE_MATRIX = {
        True: "a_verifier",
        False: "non_concerne",
    }

    def get_result_data(self):
        if self.hedges.prop("ripisylve").length:
            return True

        return False


class LoiSurLeauHaieL3503(LoiSurLeauHaieHru):
    category = HedgeCategory.l350_3
