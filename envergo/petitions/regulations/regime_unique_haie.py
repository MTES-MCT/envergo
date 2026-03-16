from envergo.moulinette.regulations.regime_unique_haie import RegimeUniqueHaie
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(RegimeUniqueHaie)
def regime_unique_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette
):
    """Build density context for the régime unique haie instructor view."""
    return {
        "density_400": moulinette.catalog.get("density_400"),
        "density_400_length": moulinette.catalog.get("density_400_length"),
        "density_400_area_ha": moulinette.catalog.get("density_400_area_ha"),
        "hedge_data_id": petition_project.hedge_data.id,
    }
