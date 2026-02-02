from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator


class SitesClassesRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Sites classés"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "autorisation",
        "non_concerne": "declaration",
    }


class SitesClassesHaie(CriterionEvaluator):
    choice_label = "Sites classés > Sites classés Haie"
    slug = "sites_classes_haie"
    plantation_conditions = []

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "non_concerne": RESULTS.non_concerne,
    }

    CODE_MATRIX = {
        True: "soumis",
        False: "non_concerne",
    }

    def get_catalog_data(self):
        data = super().get_catalog_data()
        data["aa_only"] = all(
            h.hedge_type == "alignement" for h in self.catalog["haies"].hedges()
        )
        return data

    def get_result_data(self):
        """Check if any hedge (to remove or to plant) intersects the activation map.

        If we are evaluating this criterion, it means that the criterion was activated,
        which implies that at least one hedge intersects the perimeter.
        """
        return True
