import logging

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import PlantationConditionMixin, TreeAlignmentsCondition
from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator

logger = logging.getLogger(__name__)


class AlignementArbresRegulation(HaieRegulationEvaluator):
    choice_label = "Alignements d'arbres"

    PROCEDURE_TYPE_MATRIX = {
        "soumis_autorisation": "declaration",
        "soumis_declaration": "declaration",
        "non_soumis": "declaration",
    }


class AlignementsArbres(PlantationConditionMixin, CriterionEvaluator):

    choice_label = "Alignements d'arbres > L250-3"
    slug = "alignement_arbres"
    plantation_conditions = [TreeAlignmentsCondition]

    RESULT_MATRIX = {
        "non_soumis": RESULTS.non_soumis,
        "soumis_securite": RESULTS.soumis_declaration,
        "soumis_esthetique": RESULTS.soumis_declaration,
        "soumis_autorisation": RESULTS.soumis_autorisation,
    }

    CODE_MATRIX = {
        (True, "amelioration_culture"): "soumis_autorisation",
        (True, "chemin_acces"): "soumis_autorisation",
        (True, "securite"): "soumis_securite",
        (True, "amenagement"): "soumis_autorisation",
        (True, "amelioration_ecologique"): "soumis_autorisation",
        (True, "embellissement"): "soumis_esthetique",
        (True, "autre"): "soumis_autorisation",
        (False, "amelioration_culture"): "non_soumis",
        (False, "chemin_acces"): "non_soumis",
        (False, "securite"): "non_soumis",
        (False, "amenagement"): "non_soumis",
        (False, "amelioration_ecologique"): "non_soumis",
        (False, "embellissement"): "non_soumis",
        (False, "autre"): "non_soumis",
    }

    def get_result_data(self):
        motif = self.catalog.get("motif")
        haies = self.catalog.get("haies")
        has_alignement_bord_voie = False
        if haies:
            has_alignement_bord_voie = any(
                hedge
                for hedge in haies.hedges_to_remove()
                if hedge.hedge_type == "alignement" and hedge.prop("bord_voie")
            )

        return has_alignement_bord_voie, motif

    def get_replantation_coefficient(self):
        haies = self.catalog.get("haies")
        minimum_length_to_plant = 0.0
        aggregated_r = 0.0

        r_aa = self.get_result_based_replantation_coefficient(self.result_code)

        if haies:
            for hedge in haies.hedges_to_remove():
                if hedge.hedge_type == "alignement" and hedge.prop("bord_voie"):
                    r = r_aa
                else:
                    r = 0.0

                minimum_length_to_plant = minimum_length_to_plant + hedge.length * r

            if haies.length_to_remove() > 0:
                aggregated_r = minimum_length_to_plant / haies.length_to_remove()

        return aggregated_r

    @classmethod
    def get_result_based_replantation_coefficient(cls, result_code):
        if result_code == "soumis_autorisation":
            r_aa = 2.0
        elif result_code == "soumis_esthetique":
            r_aa = 1.0
        elif result_code == "soumis_securite":
            r_aa = 1.0
        else:  # non_soumis
            r_aa = 0.0
        return r_aa
