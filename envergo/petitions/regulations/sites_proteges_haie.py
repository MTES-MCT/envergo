from envergo.hedges.models import HedgeList
from envergo.moulinette.regulations.sites_proteges_haie import SitesProtegesRegulation
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(SitesProtegesRegulation)
def sites_proteges_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    """Return context for sites proteges regulation instructor view"""

    hedges = HedgeList()

    for (
        regulation,
        perimeters,
    ) in moulinette.hedges_intersecting_regulations_perimeter.items():
        if regulation.slug != "sites_proteges_haie":
            continue

        hedges += {
            hedge
            for _, perimeter in perimeters.items()
            for _, hedges in perimeter.items()
            for hedge in hedges
        }

    return {
        "sites_proteges_hedges": hedges,
    }
