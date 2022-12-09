from functools import cached_property

from model_utils.choices import Choices

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import MoulinetteCriterion, MoulinetteRegulation

RESULTS = Choices(
    ("systematique", "Systématique"),
    ("cas_par_cas", "Cas par cas"),
    ("non_soumis", "Non soumis"),
)


class Emprise(MoulinetteCriterion):
    slug = "emprise"
    title = "Emprise au sol créée"
    choice_label = "Éval Env > Emprise"
    subtitle = ""
    header = ""

    def get_catalog_data(self):
        data = {}
        return data

    @property
    def result_code(self):
        """Return the unique result code"""
        return RESULTS.systematique

    @cached_property
    def result(self):
        """Run the check for the 3.3.1.0 rule.

        Associate a unique result code with a value from the RESULTS enum.
        """

        code = self.result_code
        result_matrix = {
            "systematique": RESULTS.systematique,
        }
        result = result_matrix[code]
        return result


class EvalEnvironnementale(MoulinetteRegulation):
    slug = "eval_env"
    title = "Évaluation Environnementale"
    criterion_classes = [Emprise]

    @cached_property
    def result(self):
        results = [criterion.result for criterion in self.criterions]

        if RESULTS.systematique in results:
            result = RESULTS.systematique
        elif RESULTS.cas_par_cas in results:
            result = RESULTS.cas_par_cas
        else:
            result = RESULTS.non_soumis

        return result
