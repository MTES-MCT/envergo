from envergo.geodata.utils import get_google_maps_centered_url, get_ign_centered_url
from envergo.hedges.regulations import TreeAlignmentsCondition
from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.regulations.alignementarbres import AlignementsArbres
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(AlignementsArbres)
def alignement_arbres_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:

    hedge_data = petition_project.hedge_data
    R = evaluator.get_replantation_coefficient()

    length_to_remove_aa_bord_voie = hedge_data.length_to_remove_aa_bord_voie()
    length_to_plant_aa_bord_voie = hedge_data.length_to_plant_aa_bord_voie()

    evaluator_context = (
        TreeAlignmentsCondition(hedge_data, R, evaluator, catalog=moulinette.catalog)
        .evaluate()
        .context
    )

    minimum_length_to_plant_aa_bord_voie = evaluator_context[
        "minimum_length_to_plant_aa_bord_voie"
    ]
    missing_plantation_length = evaluator_context["aa_bord_voie_delta"]
    if missing_plantation_length < 0:
        missing_plantation_length = 0

    motif = moulinette.catalog.get("motif", "")

    context = {
        "motif": next((v[1] for v in MOTIF_CHOICES if v[0] == motif), motif),
        "replantation_coefficient": R,
        "length_to_remove_aa_bord_voie": length_to_remove_aa_bord_voie,
        "length_to_remove_aa_non_bord_voie": 12,
        "length_to_remove_non_aa_bord_voie": 17,
        "length_to_plant_aa_bord_voie": length_to_plant_aa_bord_voie,
        "minimum_length_to_plant_aa_bord_voie": minimum_length_to_plant_aa_bord_voie,
        "missing_plantation_length": missing_plantation_length,
        "ign_url": get_ign_centered_url(petition_project.hedge_data),
        "google_maps_url": get_google_maps_centered_url(petition_project.hedge_data),
    }

    return context
