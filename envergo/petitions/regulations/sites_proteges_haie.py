from envergo.hedges.models import HEDGE_TYPES, TO_PLANT, TO_REMOVE
from envergo.moulinette.regulations.sites_proteges_haie import SitesProtegesRegulation
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(SitesProtegesRegulation)
def sites_proteges_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    """Return context for sites proteges regulation instructor view"""

    rows = HEDGE_TYPES + (("total", "total"),)

    hedges_by_type = {
        hedge_type: {
            TO_PLANT: {"length": 0.0, "ids": []},
            TO_REMOVE: {"length": 0.0, "ids": []},
        }
        for hedge_type, _ in rows
    }

    for (
        regulation,
        perimeters,
    ) in moulinette.hedges_intersecting_regulations_perimeter.items():
        if regulation.slug != "sites_proteges_haie":
            continue

        all_hedges = {
            hedge
            for _, perimeter in perimeters.items()
            for _, hedges in perimeter.items()
            for hedge in hedges
        }

        for hedge in all_hedges:
            hedges_by_type[hedge.hedge_type][hedge.type]["ids"].append(hedge.id)
            hedges_by_type[hedge.hedge_type][hedge.type]["length"] += hedge.length

            hedges_by_type["total"][hedge.type]["ids"].append(hedge.id)
            hedges_by_type["total"][hedge.type]["length"] += hedge.length

    for row, _ in rows:
        hedges_by_type[row][TO_PLANT]["ids"].sort()
        hedges_by_type[row][TO_REMOVE]["ids"].sort()

    return {
        "sites_proteges_hedges": hedges_by_type,
    }
