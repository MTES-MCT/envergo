from django.utils.module_loading import import_string

from envergo.moulinette.regulations.conditionnalitepac import Bcae8
from envergo.petitions.regulations import evaluator_instructor_view_context_getter
from envergo.petitions.services import HedgeList


@evaluator_instructor_view_context_getter(Bcae8)
def bcae8_get_instructor_view_context(evaluator, petition_project, moulinette) -> dict:
    """Build context for BCAE8 instructor page view"""

    hedge_data = petition_project.hedge_data
    lineaire_detruit_pac = hedge_data.lineaire_detruit_pac()
    lineaire_to_plant_pac = hedge_data.length_to_plant_pac()
    lineaire_total = moulinette.catalog.get("lineaire_total", "")

    hedge_to_plant_properties_form = import_string(
        moulinette.config.hedge_to_plant_properties_form
    )

    has_mode_replantation = (
        "mode_replantation" in hedge_to_plant_properties_form.base_fields
    )

    context = {
        "lineaire_detruit_pac": lineaire_detruit_pac,
        "lineaire_to_plant_pac": lineaire_to_plant_pac,
    }

    if lineaire_detruit_pac:
        context["pac_destruction_detail"] = HedgeList(hedge_data.hedges_to_remove_pac())
        context["percentage_pac"] = (
            lineaire_detruit_pac / lineaire_total * 100 if lineaire_total else ""
        )

    if lineaire_to_plant_pac:
        context["pac_plantation_detail"] = HedgeList(hedge_data.hedges_to_plant_pac())
        context["replanting_ratio"] = (
            lineaire_to_plant_pac / lineaire_detruit_pac
            if lineaire_detruit_pac > 0
            else ""
        )
        context["replanting_ratio_comment"] = (
            "Linéaire plantation nouvelle ou remplacement / linéaire à détruire, sur parcelle PAC"
            if has_mode_replantation
            else "Linéaire à planter / linéaire à détruire, sur parcelle PAC"
        )

    return context
