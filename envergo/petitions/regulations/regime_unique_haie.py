from envergo.hedges.models import HedgeCategory
from envergo.hedges.regulations import RUQualityCondition
from envergo.moulinette.regulations.regime_unique_haie import RegimeUniqueHaieRu
from envergo.moulinette.regulations.utils import (
    build_ru_hedge_detail_rows,
    collect_zone_configs,
)
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(RegimeUniqueHaieRu)
def regime_unique_haie_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build régime unique haie parameters for the instructor view."""
    context = {
        "replantation_coefficient": evaluator.get_replantation_coefficient(),
        "HedgeCategory": HedgeCategory,
    }

    context["ru_zone_configs"] = collect_zone_configs(
        moulinette.catalog.get("ru_hedge_data", {})
    )

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
