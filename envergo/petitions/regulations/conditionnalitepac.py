from django.utils.module_loading import import_string

from envergo.hedges.models import TO_PLANT, TO_REMOVE
from envergo.moulinette.regulations.conditionnalitepac import (
    Bcae8BeforeRu,
    Bcae8Hru,
    Bcae8L3503,
    Bcae8Ru,
)
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(Bcae8BeforeRu)
def bcae8_before_ru_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for BCAE8 instructor page view."""

    hedge_data = petition_project.hedge_data
    to_plant_pac = hedge_data.hedges().to_plant().pac()
    to_remove_pac = hedge_data.hedges().to_remove().pac()
    lineaire_detruit_pac = to_remove_pac.length
    lineaire_to_plant_pac = to_plant_pac.length
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
        context["pac_destruction_detail"] = to_remove_pac
        context["percentage_pac"] = (
            lineaire_detruit_pac / lineaire_total * 100 if lineaire_total else ""
        )

    if lineaire_to_plant_pac:
        context["pac_plantation_detail"] = to_plant_pac
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


@evaluator_instructor_view_context_getter(Bcae8Ru)
@evaluator_instructor_view_context_getter(Bcae8Hru)
@evaluator_instructor_view_context_getter(Bcae8L3503)
def bcae8_get_instructor_view_context(
    evaluator, petition_project, moulinette, plantation_evaluation=None
) -> dict:
    """Build context for BCAE8 instructor page view."""

    hedge_data = petition_project.hedge_data
    pac_hedges = hedge_data.hedges().prop("sur_parcelle_pac")
    non_pac_hedges = hedge_data.hedges().prop("!sur_parcelle_pac")

    pac_hedges_ru = pac_hedges.ru()
    non_pac_hedges_ru = non_pac_hedges.ru()

    pac_hedges_aa = pac_hedges.alignement()
    non_pac_hedges_aa = non_pac_hedges.alignement()

    pac_hedges_hru_not_aa = pac_hedges.hru().n_alignement()
    non_pac_hedges_hru_not_aa = non_pac_hedges.hru().n_alignement()

    pac_hedges_details = {
        "Haies régime unique": {
            "pac": {
                TO_PLANT: pac_hedges_ru.to_plant(),
                TO_REMOVE: pac_hedges_ru.to_remove(),
            },
            "non_pac": {
                TO_PLANT: non_pac_hedges_ru.to_plant(),
                TO_REMOVE: non_pac_hedges_ru.to_remove(),
            },
        },
        "Alignements d'arbres": {
            "pac": {
                TO_PLANT: pac_hedges_aa.to_plant(),
                TO_REMOVE: pac_hedges_aa.to_remove(),
            },
            "non_pac": {
                TO_PLANT: non_pac_hedges_aa.to_plant(),
                TO_REMOVE: non_pac_hedges_aa.to_remove(),
            },
        },
        "Haies hors régime uniques": {
            "pac": {
                TO_PLANT: pac_hedges_hru_not_aa.to_plant(),
                TO_REMOVE: pac_hedges_hru_not_aa.to_remove(),
            },
            "non_pac": {
                TO_PLANT: non_pac_hedges_hru_not_aa.to_plant(),
                TO_REMOVE: non_pac_hedges_hru_not_aa.to_remove(),
            },
        },
    }

    return {
        "pac_hedges_details": pac_hedges_details,
    }
