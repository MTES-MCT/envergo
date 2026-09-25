from envergo.hedges.models import HedgeList


def get_regulation_hedges_length_in_perimeter(moulinette, regulation_slug):
    """Build a HedgeList for a perimeter-based regulation.

    Each hedge's length is reduced to its intersection with the union of the
    regulation's perimeters, so a hedge covered by more than one perimeter is
    only counted once.
    """
    for (
        regulation,
        perimeters,
    ) in moulinette.hedges_intersecting_regulations_perimeter.items():
        if regulation.slug != regulation_slug:
            continue

        hedges = HedgeList(
            sorted(
                {
                    hedge
                    for hedges_by_type in perimeters.values()
                    for hedge_list in hedges_by_type.values()
                    for hedge in hedge_list
                },
                key=lambda h: h.id,
            )
        )
        return regulation.perimeters.clip(hedges)

    return HedgeList()
