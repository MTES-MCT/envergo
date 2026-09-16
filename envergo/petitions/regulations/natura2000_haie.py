from envergo.hedges.models import HedgeList
from envergo.moulinette.regulations.natura2000_haie import Natura2000HaieRegulation
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(Natura2000HaieRegulation)
def natura2000_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for the Natura 2000 haie regulation instructor view."""

    hedges = HedgeList()

    for (
        regulation,
        perimeters,
    ) in moulinette.hedges_intersecting_regulations_perimeter.items():
        if regulation.slug != "natura2000_haie":
            continue

        hedges += {
            hedge
            for _, perimeter in perimeters.items()
            for _, hedges_by_type in perimeter.items()
            for hedge in hedges_by_type
        }

    return {
        "natura2000_hedges": hedges,
    }
