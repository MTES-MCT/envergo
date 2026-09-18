from envergo.moulinette.regulations.reserves_naturelles import (
    ReservesNaturellesRegulation,
)
from envergo.petitions.regulations import evaluator_instructor_view_context_getter
from envergo.petitions.regulations.perimeter_hedges import (
    get_regulation_hedges_length_in_perimeter,
)


@evaluator_instructor_view_context_getter(ReservesNaturellesRegulation)
def reserves_naturelles_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for réserves naturelles regulation instructor view."""

    hedges = get_regulation_hedges_length_in_perimeter(
        moulinette, "reserves_naturelles"
    )

    return {
        "reserves_naturelles_hedges": hedges,
    }
