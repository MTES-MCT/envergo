import logging

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator

logger = logging.getLogger(__name__)


class AlignementsArbres(CriterionEvaluator):
    choice_label = "Alignements d'arbres  > L350-3"
    slug = "alignement_arbres"
    plantation_conditions = []

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
