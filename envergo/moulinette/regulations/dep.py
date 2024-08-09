from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator


class DerogationEspecesProtegees(CriterionEvaluator):
    choice_label = "DEP > Dérogation espèces protégées"
    slug = "dep"

    CODES = [
        "soumis",
    ]

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
    }

    def get_result_data(self):
        return "soumis"
