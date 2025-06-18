from envergo.moulinette.regulations.alignementarbres import AlignementsArbres
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(AlignementsArbres)
def alignement_arbres_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    return {}
