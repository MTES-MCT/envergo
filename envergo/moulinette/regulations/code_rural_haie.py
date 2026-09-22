from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class CodeRuralHaieRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Code rural"

    PROCEDURE_TYPE_MATRIX = {
        "a_verifier": "declaration",
    }


class CodeRuralHru(HaieCriterionEvaluator):
    choice_label = "Code rural > Code Rural L126-3"
    base_slug = "code_rural"
    category = HedgeCategory.hru

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"


class CodeRuralRu(CodeRuralHru):
    category = HedgeCategory.ru


class CodeRuralL3503(CodeRuralHru):
    category = HedgeCategory.l350_3
