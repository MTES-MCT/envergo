from decimal import Decimal as D

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import (
    PlantationConditionMixin,
    QualityCondition,
    SafetyCondition,
)
from envergo.moulinette.regulations import CriterionEvaluator


class EPMixin:
    """Legacy criterion for protected species."""

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            catalog["protected_species"] = haies.get_all_species()
        return catalog


class EspecesProtegeesSimple(PlantationConditionMixin, EPMixin, CriterionEvaluator):
    """Basic criterion: always returns "soumis."""

    choice_label = "EP > EP simple"
    slug = "ep_simple"
    plantation_conditions = [SafetyCondition]

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_result_data(self):
        return "soumis"


class EspecesProtegeesAisne(PlantationConditionMixin, EPMixin, CriterionEvaluator):
    """Check for protected species living in hedges."""

    choice_label = "EP > EP Aisne"
    slug = "ep_aisne"
    plantation_conditions = [SafetyCondition, QualityCondition]

    CODE_MATRIX = {
        (False, True): "interdit",
        (False, False): "interdit",
        (True, True): "derogation_inventaire",
        (True, False): "derogation_simplifiee",
    }

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "derogation_inventaire": RESULTS.derogation_inventaire,
        "derogation_simplifiee": RESULTS.derogation_simplifiee,
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            species = haies.get_all_species()
            catalog["protected_species"] = species
            catalog["fauna_sensitive_species"] = [
                s for s in species if s.highly_sensitive and s.kingdom == "animalia"
            ]
            catalog["flora_sensitive_species"] = [
                s for s in species if s.highly_sensitive and s.kingdom == "plantae"
            ]
        return catalog

    def get_result_data(self):
        has_reimplantation = self.catalog.get("reimplantation") != "non"
        has_sensitive_species = False
        species = self.catalog.get("protected_species")
        for s in species:
            if s.highly_sensitive:
                has_sensitive_species = True
                break

        return has_reimplantation, has_sensitive_species

    def get_replantation_coefficient(self):
        return D("1.5")
