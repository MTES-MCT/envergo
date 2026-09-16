from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class SitesProtegesRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Sites protégés"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "autorisation",
        "non_concerne": "declaration",
    }


class SitesPatrimoniauxRemarquablesHaieHru(HaieCriterionEvaluator):
    choice_label = "Sites protégés > SPR Haie"
    base_slug = "spr_haie"
    category = HedgeCategory.hru
    plantation_conditions = []

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"


class SitesPatrimoniauxRemarquablesHaieRu(SitesPatrimoniauxRemarquablesHaieHru):
    category = HedgeCategory.ru


class SitesPatrimoniauxRemarquablesHaieL3503(SitesPatrimoniauxRemarquablesHaieHru):
    category = HedgeCategory.l350_3


class MonumentsHistoriquesHaieHru(HaieCriterionEvaluator):
    choice_label = "Sites protégés > MH Haie"
    base_slug = "mh_haie"
    category = HedgeCategory.hru
    plantation_conditions = []

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"


class MonumentsHistoriquesHaieRu(MonumentsHistoriquesHaieHru):
    category = HedgeCategory.ru


class MonumentsHistoriquesHaieL3503(MonumentsHistoriquesHaieHru):
    category = HedgeCategory.l350_3
