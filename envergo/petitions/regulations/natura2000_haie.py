from envergo.moulinette.regulations.natura2000_haie import Natura2000HaieRegulation
from envergo.petitions.regulations import evaluator_instructor_view_context_getter
from envergo.petitions.regulations.perimeter_hedges import (
    get_regulation_hedges_length_in_perimeter,
)


@evaluator_instructor_view_context_getter(Natura2000HaieRegulation)
def natura2000_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for the Natura 2000 haie regulation instructor view."""

    hedges = get_regulation_hedges_length_in_perimeter(moulinette, "natura2000_haie")
    return {
        "natura2000_hedges": hedges,
    }
