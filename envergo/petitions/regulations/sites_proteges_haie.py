from envergo.moulinette.regulations.sites_proteges_haie import SitesProtegesRegulation
from envergo.petitions.regulations import evaluator_instructor_view_context_getter
from envergo.petitions.regulations.perimeter_hedges import (
    get_regulation_hedges_length_in_perimeter,
)


@evaluator_instructor_view_context_getter(SitesProtegesRegulation)
def sites_proteges_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for sites protégés regulation instructor view."""

    hedges = get_regulation_hedges_length_in_perimeter(
        moulinette, "sites_proteges_haie"
    )
    return {
        "sites_proteges_hedges": hedges,
    }
