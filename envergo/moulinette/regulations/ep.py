from decimal import Decimal as D

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HEDGE_TYPES
from envergo.hedges.regulations import (
    PlantationConditionMixin,
    QualityCondition,
    SafetyCondition,
)
from envergo.moulinette.regulations import CriterionEvaluator
from envergo.utils.fields import get_human_readable_value


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


def get_hedge_compensation_details(hedge, r):
    hedge_properties = []
    if hedge.prop("essences_non_bocageres"):
        hedge_properties.append("essences non bocagères")
    if hedge.prop("recemment_plantee"):
        hedge_properties.append("récemment plantée")

    return {
        "id": hedge.id,
        "hedge_type": get_human_readable_value(HEDGE_TYPES, hedge.hedge_type),
        "properties": ", ".join(hedge_properties) if hedge_properties else "-",
        "length": hedge.length,
        "r": r,
    }


class EspecesProtegeesNormandie(PlantationConditionMixin, EPMixin, CriterionEvaluator):
    """Check for protected species living in hedges."""

    choice_label = "EP > EP Normandie"
    slug = "ep_normandie"
    plantation_conditions = [SafetyCondition]

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "interdit_remplacement": RESULTS.interdit,
        "derogation_simplifiee": RESULTS.derogation_simplifiee,
        "dispense_coupe_a_blanc": RESULTS.dispense_sous_condition,
        "dispense_20m": RESULTS.dispense_sous_condition,
        "dispense_10m": RESULTS.dispense,
    }

    CODE_MATRIX = {
        ("0", False, "non"): "dispense_10m",
        ("0", False, "remplacement"): "dispense_10m",
        ("0", False, "replantation"): "dispense_10m",
        ("lte_1", False, "non"): "interdit",
        ("lte_1", False, "remplacement"): "dispense_20m",
        ("lte_1", False, "replantation"): "dispense_20m",
        ("gt_1", False, "non"): "interdit",
        ("gt_1", False, "remplacement"): "interdit_remplacement",
        ("gt_1", False, "replantation"): "derogation_simplifiee",
        ("0", True, "non"): "dispense_10m",
        ("0", True, "remplacement"): "dispense_10m",
        ("0", True, "replantation"): "dispense_10m",
        ("lte_1", True, "non"): "interdit",
        ("lte_1", True, "remplacement"): "dispense_coupe_a_blanc",
        ("lte_1", True, "replantation"): "dispense_20m",
        ("gt_1", True, "non"): "interdit",
        ("gt_1", True, "remplacement"): "dispense_coupe_a_blanc",
        ("gt_1", True, "replantation"): "derogation_simplifiee",
    }

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        all_r = []
        hedges_details = []
        coupe_a_blanc_every_hedge = True
        reimplantation = self.catalog.get("reimplantation")
        minimum_length_to_plant = 0.0
        aggregated_r = 0.0

        if haies:
            for hedge in haies.hedges_to_remove():
                if hedge.mode_destruction != "coupe_a_blanc":
                    coupe_a_blanc_every_hedge = False

                if hedge.length <= 10:
                    r = 0
                elif hedge.length <= 20:
                    r = 1
                elif (
                    reimplantation == "remplacement"
                    and hedge.mode_destruction == "coupe_a_blanc"
                ):
                    r = 1
                else:
                    r = 2
                all_r.append(r)
                minimum_length_to_plant = minimum_length_to_plant + hedge.length * r
                hedges_details.append(get_hedge_compensation_details(hedge, r))

            if haies.length_to_remove() > 0:
                aggregated_r = minimum_length_to_plant / haies.length_to_remove()

        r_max = max(all_r) if all_r else self.get_replantation_coefficient()
        catalog["r_max"] = r_max
        catalog["coupe_a_blanc_every_hedge"] = coupe_a_blanc_every_hedge
        catalog["aggregated_r"] = aggregated_r
        catalog["hedges_compensation_details"] = hedges_details
        return catalog

    def get_result_data(self):
        reimplantation = self.catalog.get("reimplantation")
        r_max = self.catalog.get("r_max")
        coupe_a_blanc_every_hedge = self.catalog.get("coupe_a_blanc_every_hedge")
        r_max_value = "0" if r_max == 0 else "lte_1" if r_max <= 1 else "gt_1"

        return r_max_value, coupe_a_blanc_every_hedge, reimplantation

    def get_replantation_coefficient(self):
        return self.catalog.get("aggregated_r")
