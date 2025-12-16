from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator


class SitesProtegesRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Sites protégés"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "autorisation",
        "non_concerne": "declaration",
    }


class SitesPatrimoniauxRemarquablesHaie(CriterionEvaluator):
    choice_label = "Sites protégés > SPR Haie"
    slug = "spr_haie"
    plantation_conditions = []

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["aa_only"] = all(
            h.hedge_type == "alignement" for h in self.catalog["haies"].hedges()
        )
        return data

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"


class MonumentsHistoriquesHaie(CriterionEvaluator):
    choice_label = "Sites protégés > MH Haie"
    slug = "mh_haie"
    plantation_conditions = []

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["aa_only"] = all(
            h.hedge_type == "alignement" for h in self.catalog["haies"].hedges()
        )
        return data

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"
