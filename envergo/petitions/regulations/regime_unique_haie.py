from envergo.moulinette.regulations.regime_unique_haie import RegimeUniqueHaie
from envergo.petitions.regulations import (
    evaluator_instructor_view_context_getter,
    get_line_buffer_density_context,
)


@evaluator_instructor_view_context_getter(RegimeUniqueHaie)
def regime_unique_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette
):
    """Build density context for the régime unique haie instructor view."""
    return get_line_buffer_density_context(petition_project, moulinette)
