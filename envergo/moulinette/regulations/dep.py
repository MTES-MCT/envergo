from envergo.moulinette.regulations import CriterionEvaluator


class DerogationEspecesProtegees(CriterionEvaluator):
    choice_label = "DEP > DEP"
    slug = "dep"

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_result_data(self):
        return "soumis"
