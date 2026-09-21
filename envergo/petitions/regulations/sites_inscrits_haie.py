from envergo.moulinette.regulations.sites_inscrits_haie import SitesInscritsRegulation
from envergo.petitions.regulations import evaluator_instructor_view_context_getter
from envergo.petitions.regulations.perimeter_hedges import (
    get_regulation_hedges_length_in_perimeter,
)


@evaluator_instructor_view_context_getter(SitesInscritsRegulation)
def sites_inscrits_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for sites inscrits regulation instructor view."""

    hedges = get_regulation_hedges_length_in_perimeter(
        moulinette, "sites_inscrits_haie"
    )
    return {
        "sites_inscrits_hedges": hedges,
    }
