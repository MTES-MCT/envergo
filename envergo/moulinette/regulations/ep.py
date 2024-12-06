from envergo.moulinette.regulations import CriterionEvaluator


class EspecesProtegees(CriterionEvaluator):
    choice_label = "EP > EP"
    slug = "ep"

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_result_data(self):
        return "soumis"
