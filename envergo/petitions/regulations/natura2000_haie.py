from envergo.moulinette.regulations.natura2000_haie import Natura2000Haie
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(Natura2000Haie)
def n2000_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    return {}
