from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    AlignementsOnlyMixin,
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class SitesClassesRegulation(AlignementsOnlyMixin, HaieRegulationEvaluator):
    choice_label = "Haie > Sites classés"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "autorisation",
        "non_concerne": "declaration",
    }


class SitesClassesHaieHru(HaieCriterionEvaluator):
    choice_label = "Sites classés > Sites classés Haie"
    base_slug = "sites_classes_haie"
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


class SitesClassesHaieRu(SitesClassesHaieHru):
    category = HedgeCategory.ru


class SitesClassesHaieL3503(SitesClassesHaieHru):
    category = HedgeCategory.l350_3
