from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    AlignementsOnlyMixin,
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class SitesInscritsRegulation(AlignementsOnlyMixin, HaieRegulationEvaluator):
    choice_label = "Haie > Sites inscrits"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
    }


class SitesInscritsHaieHru(HaieCriterionEvaluator):
    choice_label = "Sites inscrits > Sites inscrits Haie"
    base_slug = "si_haie"
    category = HedgeCategory.hru
    plantation_conditions = []

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "non_concerne": RESULTS.non_concerne,
    }

    CODE_MATRIX = {
        True: "soumis",
        False: "non_concerne",
    }

    def get_result_data(self):
        """Check if any hedge (to remove or to plant) intersects the activation map.

        If we are evaluating this criterion, it means that the criterion was activated,
        which implies that at least one hedge intersects the perimeter.
        """
        return True


class SitesInscritsHaieRu(SitesInscritsHaieHru):
    category = HedgeCategory.ru


class SitesInscritsHaieL3503(SitesInscritsHaieHru):
    category = HedgeCategory.l350_3
