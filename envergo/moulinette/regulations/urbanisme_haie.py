from envergo.moulinette.regulations import CriterionEvaluator


class UrbanismeHaie(CriterionEvaluator):
    choice_label = "Urbanisme Haie > Urbanisme Haie"
    slug = "urbanisme_haie"

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"
