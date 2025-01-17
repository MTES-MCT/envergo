from envergo.moulinette.regulations import CriterionEvaluator


class EspecesProtegees(CriterionEvaluator):
    choice_label = "EP > EP"
    slug = "ep"

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            catalog["protected_species"] = haies.get_all_species()
        return catalog

    def get_result_data(self):
        return "soumis"
