from envergo.hedges.regulations import RUQualityCondition
from envergo.moulinette.regulations.regime_unique_haie import (
    RegimeUniqueHaie,
    build_ru_hedge_detail_rows,
    get_ru_debug_context,
)
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(RegimeUniqueHaie)
def regime_unique_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build régime unique haie parameters for the instructor view."""
    context = {
        "replantation_coefficient": evaluator.get_replantation_coefficient(),
    }

    ru_debug = get_ru_debug_context(moulinette.catalog)
    context["ru_zone_configs"] = ru_debug["ru_zone_configs"]

    context["hedge_detail_rows"] = build_ru_hedge_detail_rows(
        moulinette.catalog, evaluator
    )

    context["quality_condition"] = {}
    if plantation_evaluation:
        condition = plantation_evaluation.find_condition(RUQualityCondition, evaluator)
        if condition:
            context["quality_condition"] = condition.context

    context["ordered_hedge_types"] = list(reversed(moulinette.hedge_types))

    return context
