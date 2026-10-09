from abc import ABC

from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    AlignementsOnlyMixin,
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class SitesProtegesRegulation(AlignementsOnlyMixin, HaieRegulationEvaluator):
    choice_label = "Haie > Sites protégés"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "autorisation",
        "non_concerne": "declaration",
    }


class SitesPatrimoniauxRemarquablesHaieBase(HaieCriterionEvaluator, ABC):
    choice_label = "Sites protégés > SPR Haie"
    base_slug = "spr_haie"
    plantation_conditions = []

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"


class SitesPatrimoniauxRemarquablesHaieHru(SitesPatrimoniauxRemarquablesHaieBase):
    category = HedgeCategory.hru


class SitesPatrimoniauxRemarquablesHaieRu(SitesPatrimoniauxRemarquablesHaieBase):
    category = HedgeCategory.ru


class SitesPatrimoniauxRemarquablesHaieL3503(SitesPatrimoniauxRemarquablesHaieBase):
    category = HedgeCategory.l350_3


class MonumentsHistoriquesHaieBase(HaieCriterionEvaluator, ABC):
    choice_label = "Sites protégés > MH Haie"
    base_slug = "mh_haie"
    plantation_conditions = []

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"


class MonumentsHistoriquesHaieHru(MonumentsHistoriquesHaieBase):
    category = HedgeCategory.hru


class MonumentsHistoriquesHaieRu(MonumentsHistoriquesHaieBase):
    category = HedgeCategory.ru


class MonumentsHistoriquesHaieL3503(MonumentsHistoriquesHaieBase):
    category = HedgeCategory.l350_3
