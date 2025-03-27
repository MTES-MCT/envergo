from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator


class Natura2000Haie(CriterionEvaluator):
    choice_label = "Natura 2000 > Haie"
    slug = "natura2000_haie"

    CODE_MATRIX = {
        True: "soumis",
    }

    RESULT_MATRIX = {
        "non_concerne": RESULTS.non_concerne,
        "non_soumis": RESULTS.non_soumis,
        "soumis": RESULTS.soumis,
    }

    def get_result_data(self):
        return True
