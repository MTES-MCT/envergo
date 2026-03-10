from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator


class CodeRuralHaieRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Code rural"

    PROCEDURE_TYPE_MATRIX = {
        "a_verifier": "declaration",
    }


class CodeRural(CriterionEvaluator):
    choice_label = "Code rural > Code Rural L126-3"
    slug = "code_rural"

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"
