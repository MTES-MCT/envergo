from collections import defaultdict
from decimal import Decimal as D

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import PlantationCondition, PlantationConditionMixin
from envergo.moulinette.regulations import CriterionEvaluator


class EPMixin:
    """Legacy criterion for protected species."""

    def get_catalog_data(self):
        catalog = super().get_catalog_data()
        haies = self.catalog.get("haies")
        if haies:
            catalog["protected_species"] = haies.get_all_species()
        return catalog

    def plantation_evaluate(self, R):
        safety_conditions = self.plantation_evaluate_safety()
        return [safety_conditions]

    def plantation_evaluate_safety(self):
        """Make sure hedges are not planted under power lines."""

        hedge_data = self.catalog["haies"]
        unsafe_hedges = [
            h
            for h in hedge_data.hedges_to_plant()
            if h.hedge_type in ["alignement", "mixte"] and h.sous_ligne_electrique
        ]
        return PlantationCondition(result=not unsafe_hedges)


class EspecesProtegeesSimple(EPMixin, CriterionEvaluator):
    """Basic criterion: always returns "soumis."""

    choice_label = "EP > EP simple"
    slug = "ep_simple"

    CODE_MATRIX = {
        "soumis": "soumis",
    }

    def get_result_data(self):
        return "soumis"


class EspecesProtegeesAisne(PlantationConditionMixin, EPMixin, CriterionEvaluator):
    """Check for protected species living in hedges."""

    choice_label = "EP > EP Aisne"
    slug = "ep_aisne"

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

    def plantation_evaluate(self, R):
        safety_condition = self.plantation_evaluate_safety()
        quality_condition = self.plantation_evaluate_quality(R)
        return [safety_condition, quality_condition]

    def plantation_evaluate_quality(self, R):
        """Evaluate the quality of the plantation project.
        The quality of the hedge planted must be at least as good as that of the hedge destroyed:
            Type 5 (mixte) hedges must be replaced by type 5 (mixte) hedges
            Type 4 (alignement) hedges must be replaced by type 4 (alignement) or 5 (mixte) hedges.
            Type 3 (arbustive) hedges must be replaced by type 3 (arbustive) hedges.
            Type 2 (buissonnante) hedges must be replaced by type 2 (buissonnante) or 3 (arbustive) hedges.
            Type 1 (degradee) hedges must be replaced by type 2 (buissonnante), 3 (arbustive) or 5 (mixte) hedges.

        return: {
            is_quality_sufficient: True if the plantation quality is sufficient, False otherwise,
            missing_plantation: {
                mixte: missing length of mixte hedges to plant,
                alignement: missing length of alignement hedges to plant,
                arbustive: missing length of arbustive hedges to plant,
                buissonante: missing length of buissonante hedges to plant,
                degradee: missing length of dégradée hedges to plant,
            }
        }
        """
        minimum_lengths_to_plant = self.get_minimum_lengths_to_plant(R)
        lengths_to_plant = self.get_lengths_to_plant()

        reliquat = {
            "mixte_remplacement_alignement": max(
                0, lengths_to_plant["mixte"] - minimum_lengths_to_plant["mixte"]
            ),
            "mixte_remplacement_dégradée": max(
                0,
                max(0, lengths_to_plant["mixte"] - minimum_lengths_to_plant["mixte"])
                - max(
                    0,
                    minimum_lengths_to_plant["alignement"]
                    - lengths_to_plant["alignement"],
                ),
            ),
            "arbustive_remplacement_buissonnante": max(
                0, lengths_to_plant["arbustive"] - minimum_lengths_to_plant["arbustive"]
            ),
            "arbustive_remplacement_dégradée": max(
                0,
                max(
                    0,
                    lengths_to_plant["arbustive"]
                    - minimum_lengths_to_plant["arbustive"],
                )
                - max(
                    0,
                    minimum_lengths_to_plant["buissonnante"]
                    - lengths_to_plant["buissonnante"],
                ),
            ),
            "buissonnante_remplacement_dégradée": max(
                0,
                lengths_to_plant["buissonnante"]
                - minimum_lengths_to_plant["buissonnante"],
            ),
        }

        missing_plantation = {
            "mixte": max(
                0, minimum_lengths_to_plant["mixte"] - lengths_to_plant["mixte"]
            ),
            "alignement": max(
                0,
                minimum_lengths_to_plant["alignement"]
                - lengths_to_plant["alignement"]
                - reliquat["mixte_remplacement_alignement"],
            ),
            "arbustive": max(
                0, minimum_lengths_to_plant["arbustive"] - lengths_to_plant["arbustive"]
            ),
            "buissonante": max(
                0,
                minimum_lengths_to_plant["buissonnante"]
                - lengths_to_plant["buissonnante"]
                - reliquat["arbustive_remplacement_buissonnante"],
            ),
            "degradee": max(
                0,
                minimum_lengths_to_plant["degradee"]
                - reliquat["mixte_remplacement_dégradée"]
                - reliquat["arbustive_remplacement_dégradée"]
                - reliquat["buissonnante_remplacement_dégradée"],
            ),
        }

        quality_condition = PlantationCondition(
            result=all(
                [
                    missing_plantation["mixte"] == 0,
                    missing_plantation["alignement"] == 0,
                    missing_plantation["arbustive"] == 0,
                    missing_plantation["buissonante"] == 0,
                    missing_plantation["degradee"] == 0,
                ]
            ),
            context={
                "missing_plantation": missing_plantation,
            },
        )
        return quality_condition

    def get_minimum_lengths_to_plant(self, R):
        hedge_data = self.catalog["haies"]
        lengths_by_type = defaultdict(int)
        for to_remove in hedge_data.hedges_to_remove():
            lengths_by_type[to_remove.hedge_type] += to_remove.length

        return {
            "degradee": R * lengths_by_type["degradee"],
            "buissonnante": R * lengths_by_type["buissonnante"],
            "arbustive": R * lengths_by_type["arbustive"],
            "mixte": R * lengths_by_type["mixte"],
            "alignement": R * lengths_by_type["alignement"],
        }

    def get_lengths_to_plant(self):
        hedge_data = self.catalog["haies"]
        lengths_by_type = defaultdict(int)
        for to_plant in hedge_data.hedges_to_plant():
            lengths_by_type[to_plant.hedge_type] += to_plant.length

        return {
            "buissonnante": lengths_by_type["buissonnante"],
            "arbustive": lengths_by_type["arbustive"],
            "mixte": lengths_by_type["mixte"],
            "alignement": lengths_by_type["alignement"],
        }
