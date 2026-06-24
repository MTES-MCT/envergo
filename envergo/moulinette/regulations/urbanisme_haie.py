from envergo.geodata.utils import get_geoportail_urbanisme_centered_url
from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class UrbanismeHaieRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Urbanisme"

    PROCEDURE_TYPE_MATRIX = {
        "a_verifier": "declaration",
    }


class UrbanismeHaieHru(HaieCriterionEvaluator):
    choice_label = "Urbanisme Haie > Urbanisme Haie"
    base_slug = "urbanisme_haie"
    category = HedgeCategory.hru

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["geoportail_url"] = get_geoportail_urbanisme_centered_url(self.hedges)
        return data


class UrbanismeHaieRu(UrbanismeHaieHru):
    category = HedgeCategory.ru


class UrbanismeHaieL3503(UrbanismeHaieHru):
    category = HedgeCategory.l350_3
