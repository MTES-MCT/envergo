from envergo.geodata.utils import get_geoportail_urbanisme_centered_url
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieCriterionScope,
    HaieRegulationEvaluator,
)


class UrbanismeHaieRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Urbanisme"

    PROCEDURE_TYPE_MATRIX = {
        "a_verifier": "declaration",
    }


class UrbanismeHaieHru(HaieCriterionEvaluator):
    choice_label = "Urbanisme Haie > Urbanisme Haie"
    slug = "urbanisme_haie"
    scope = HaieCriterionScope.hru

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["geoportail_url"] = get_geoportail_urbanisme_centered_url(
            self.catalog.get("haies")
        )
        return data


class UrbanismeHaieRu(UrbanismeHaieHru):
    scope = HaieCriterionScope.ru


class UrbanismeHaieL3503(UrbanismeHaieHru):
    scope = HaieCriterionScope.l350_3
