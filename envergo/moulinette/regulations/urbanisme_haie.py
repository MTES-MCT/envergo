from envergo.geodata.utils import get_geoportail_urbanisme_centered_url
from envergo.moulinette.regulations import CriterionEvaluator


class UrbanismeHaie(CriterionEvaluator):
    choice_label = "Urbanisme Haie > Urbanisme Haie"
    slug = "urbanisme_haie"

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["geoportail_url"] = get_geoportail_urbanisme_centered_url(
            self.catalog.get("haies")
        )
        return data
