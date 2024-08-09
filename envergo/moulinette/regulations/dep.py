from envergo.moulinette.regulations import CriterionEvaluator


class DerogationEspecesProtegees(CriterionEvaluator):
    choice_label = "DEP > Dérogation espèces protégées"
    slug = "dep"

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_result_data(self):
        return "soumis"
