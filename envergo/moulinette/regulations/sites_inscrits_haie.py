from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator


class SitesInscritsRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Sites inscrits"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
    }


class SitesInscritsHaie(CriterionEvaluator):
    choice_label = "Sites inscrits > SI Haie"
    slug = "si_haie"
    plantation_conditions = []

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["aa_only"] = all(
            h.hedge_type == "alignement" for h in self.catalog["haies"].hedges()
        )
        return data

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"
