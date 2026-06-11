from envergo.hedges.models import TO_PLANT, TO_REMOVE
from envergo.hedges.regulations import TreeAlignmentsCondition
from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.regulations.alignementarbres import (
    AlignementsArbresCalvadosBeforeRu,
    AlignementsArbresL3503,
)
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(AlignementsArbresL3503)
@evaluator_instructor_view_context_getter(AlignementsArbresCalvadosBeforeRu)
def alignement_arbres_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for alignement d'arbres regulation instructor view."""

    hedge_data = petition_project.hedge_data
    R = evaluator.get_result_based_replantation_coefficient(evaluator.result_code)

    motif = moulinette.catalog.get("motif", "")

    context = {
        "motif": next((v[1] for v in MOTIF_CHOICES if v[0] == motif), motif),
        "replantation_coefficient": R,
    }

    # Hedges to remove, alignement_arbres, en bord de voie
    hedges_to_remove_aa_bord_voie = hedge_data.hedges_filter(
        TO_REMOVE, "alignement", "bord_voie"
    )
    length_to_remove_aa_bord_voie = hedges_to_remove_aa_bord_voie.length
    context["length_to_remove_aa_bord_voie"] = length_to_remove_aa_bord_voie
    if length_to_remove_aa_bord_voie:
        context["aa_bord_voie_destruction_detail"] = hedges_to_remove_aa_bord_voie

    # Hedges to remove, alignement_arbres, not bord de voie
    hedges_to_remove_aa_non_bord_voie = hedge_data.hedges_filter(
        TO_REMOVE, "alignement", "!bord_voie"
    )
    length_to_remove_aa_non_bord_voie = hedges_to_remove_aa_non_bord_voie.length
    context["length_to_remove_aa_non_bord_voie"] = length_to_remove_aa_non_bord_voie
    if length_to_remove_aa_non_bord_voie:
        context["aa_non_bord_voie_destruction_detail"] = (
            hedges_to_remove_aa_non_bord_voie
        )

    # Hedges to remove, non alignement_arbres, en bord de voie
    hedges_to_remove_non_aa_bord_voie = hedge_data.hedges_filter(
        TO_REMOVE, "!alignement", "bord_voie"
    )
    length_to_remove_non_aa_bord_voie = hedges_to_remove_non_aa_bord_voie.length
    context["length_to_remove_non_aa_bord_voie"] = length_to_remove_non_aa_bord_voie
    if length_to_remove_non_aa_bord_voie:
        context["non_aa_bord_voie_destruction_detail"] = (
            hedges_to_remove_non_aa_bord_voie
        )

    # Hedges to plant, alignement_arbres, en bord de voie
    hedges_to_plant_aa_bord_voie = hedge_data.hedges_filter(
        TO_PLANT, "alignement", "bord_voie"
    )
    length_to_plant_aa_bord_voie = hedges_to_plant_aa_bord_voie.length
    context["length_to_plant_aa_bord_voie"] = length_to_plant_aa_bord_voie
    if length_to_plant_aa_bord_voie:
        context["aa_bord_voie_plantation_detail"] = hedges_to_plant_aa_bord_voie

    if plantation_evaluation:
        condition = plantation_evaluation.find_condition(
            TreeAlignmentsCondition, evaluator
        )
        if condition:
            condition_ctx = condition.context
            context["minimum_length_to_plant_aa_bord_voie"] = condition_ctx[
                "minimum_length_to_plant_aa_bord_voie"
            ]
            context["missing_plantation_length"] = condition_ctx["aa_bord_voie_delta"]

    return context
