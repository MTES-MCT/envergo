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


class SitesPatrimoniauxRemarquablesHaie(HaieCriterionEvaluator):
    choice_label = "Sites protégés > SPR Haie"
    base_slug = "spr_haie"
    plantation_conditions = []

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"


class MonumentsHistoriquesHaie(HaieCriterionEvaluator):
    choice_label = "Sites protégés > MH Haie"
    base_slug = "mh_haie"
    plantation_conditions = []

    def evaluate(self):
        self._result_code, self._result = "soumis", "soumis"
