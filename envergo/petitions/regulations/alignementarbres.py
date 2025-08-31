from envergo.geodata.utils import get_google_maps_centered_url, get_ign_centered_url
from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.regulations.alignementarbres import AlignementsArbres
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(AlignementsArbres)
def alignement_arbres_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:

    hedge_data = petition_project.hedge_data
    R = evaluator.get_replantation_coefficient()

    length_to_remove = hedge_data.length_to_remove()
    expected_length_to_plant = length_to_remove * R
    length_to_plant = hedge_data.length_to_plant()

    missing_plantation_length = expected_length_to_plant - length_to_plant
    if missing_plantation_length < 0:
        missing_plantation_length = 0

    motif = moulinette.catalog.get("motif", "")

    context = {
        "motif": next((v[1] for v in MOTIF_CHOICES if v[0] == motif), motif),
        "replantation_coefficient": R,
        "lineaire_detruit": length_to_remove,
        "lineaire_attendu": expected_length_to_plant,
        "lineaire_to_plant": length_to_plant,
        "missing_plantation_length": missing_plantation_length,
        "ign_url": get_ign_centered_url(petition_project.hedge_data),
        "google_maps_url": get_google_maps_centered_url(petition_project.hedge_data),
    }
    return context
