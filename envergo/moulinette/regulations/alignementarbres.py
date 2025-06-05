import logging

from envergo.evaluations.models import RESULTS
from envergo.hedges.regulations import PlantationConditionMixin, TreeAlignmentsCondition
from envergo.moulinette.regulations import CriterionEvaluator

logger = logging.getLogger(__name__)


class AlignementsArbres(PlantationConditionMixin, CriterionEvaluator):

    choice_label = "Alignements d'arbres  > L350-3"
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

        if self.result_code == "soumis_autorisation":
            r_aa = 2.0
        elif self.result_code == "soumis_esthetique":
            r_aa = 1.0
        elif self.result_code == "soumis_securite":
            r_aa = 1.0
        else:  # non_soumis
            r_aa = 0.0

        if haies:
            for hedge in haies.hedges_to_remove():
                if hedge.hedge_type == "alignement":
                    r = r_aa
                else:
                    r = 0.0

                minimum_length_to_plant = minimum_length_to_plant + hedge.length * r

            if haies.length_to_remove() > 0:
                aggregated_r = minimum_length_to_plant / haies.length_to_remove()

        return aggregated_r
