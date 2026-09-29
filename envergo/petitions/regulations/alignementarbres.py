from envergo.hedges.models import TO_PLANT, TO_REMOVE
from envergo.hedges.regulations import TreeAlignmentsCondition
from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.regulations.alignementarbres import (
    AlignementArbresRegulation,
    AlignementsArbresCalvadosBeforeRu,
    AlignementsArbresHru,
    AlignementsArbresL3503,
    AlignementsArbresRu,
)
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(AlignementArbresRegulation)
def alignement_arbres_regulation_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for alignement d'arbres regulation instructor view."""
    hedge_data = petition_project.hedge_data

    motif = moulinette.catalog.get("motif", "")
    context = {
        "motif": next((v[1] for v in MOTIF_CHOICES if v[0] == motif), motif),
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

    return context


@evaluator_instructor_view_context_getter(AlignementsArbresL3503)
@evaluator_instructor_view_context_getter(AlignementsArbresCalvadosBeforeRu)
@evaluator_instructor_view_context_getter(AlignementsArbresHru)
@evaluator_instructor_view_context_getter(AlignementsArbresRu)
def alignement_arbres_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for alignement d'arbres regulation instructor view."""

    R = (
        evaluator.get_result_based_replantation_coefficient()
        if hasattr(evaluator, "get_result_based_replantation_coefficient")
        else None
    )
    context = {
        "replantation_coefficient": R,
    }
    if plantation_evaluation:
        condition = plantation_evaluation.find_condition(
            TreeAlignmentsCondition, evaluator
        )
        if condition:
            condition_ctx = condition.context
            context["minimum_length_to_plant_aa_bord_voie"] = condition_ctx[
                "minimum_length_to_plant_aa_bord_voie"
            ]
            context["length_to_plant_aa_bord_voie"] = (
                evaluator.hedges.to_plant().l350_3().length
            )
            context["missing_plantation_length"] = condition_ctx["aa_bord_voie_delta"]

    return context
