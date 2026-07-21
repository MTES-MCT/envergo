from envergo.moulinette.regulations.loi_sur_leau_haie import LoiSurLeauHaieRegulation
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(LoiSurLeauHaieRegulation)
def loi_sur_leau_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for loi sur l'eau regulation instructor view."""

    return {
        "ripisylve_hedges": moulinette.catalog["haies"].hedges().prop("ripisylve"),
    }
