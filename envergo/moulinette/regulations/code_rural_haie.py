from abc import ABC

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


class CodeRuralBase(HaieCriterionEvaluator, ABC):
    choice_label = "Code rural > Code Rural L126-3"
    base_slug = "code_rural"

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"


class CodeRuralHru(CodeRuralBase):
    category = HedgeCategory.hru


class CodeRuralRu(CodeRuralBase):
    category = HedgeCategory.ru


class CodeRuralL3503(CodeRuralBase):
    category = HedgeCategory.l350_3
