from envergo.moulinette.regulations.reserves_naturelles import ReservesNaturelles
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(ReservesNaturelles)
def reserves_naturelles_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    """Return context for reserves_naturelles regulation instructor view"""
    return {}
