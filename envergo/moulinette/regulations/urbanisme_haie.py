from abc import ABC

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


class UrbanismeHaieBase(HaieCriterionEvaluator, ABC):
    choice_label = "Urbanisme Haie > Urbanisme Haie"
    base_slug = "urbanisme_haie"

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["geoportail_url"] = get_geoportail_urbanisme_centered_url(self.hedges)
        return data


class UrbanismeHaieHru(UrbanismeHaieBase):
    category = HedgeCategory.hru


class UrbanismeHaieRu(UrbanismeHaieBase):
    category = HedgeCategory.ru


class UrbanismeHaieL3503(UrbanismeHaieBase):
    category = HedgeCategory.l350_3
