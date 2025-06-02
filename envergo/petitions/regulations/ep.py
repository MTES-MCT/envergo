from django.forms import ChoiceField
from django.utils.module_loading import import_string

from envergo.hedges.models import TO_PLANT, TO_REMOVE
from envergo.moulinette.forms.fields import DisplayFieldMixin
from envergo.moulinette.regulations.ep import (
    EspecesProtegeesAisne,
    EspecesProtegeesNormandie,
    EspecesProtegeesSimple,
)
from envergo.petitions.regulations import evaluator_instructor_view_context_getter
from envergo.petitions.services import HedgeList


@evaluator_instructor_view_context_getter(EspecesProtegeesNormandie)
def ep_normandie_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    context = ep_base_get_instructor_view_context(
        evaluator, petition_project, moulinette
    )
    context["replantation_coefficient"] = evaluator.get_replantation_coefficient()
    return context


@evaluator_instructor_view_context_getter(EspecesProtegeesAisne)
def ep_aisne_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    context = ep_base_get_instructor_view_context(
        evaluator, petition_project, moulinette
    )
    context["replantation_coefficient"] = evaluator.get_replantation_coefficient()
    return context


@evaluator_instructor_view_context_getter(EspecesProtegeesSimple)
def ep_simple_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    """Build Espèces Protégées informations for instructor page view"""
    return ep_base_get_instructor_view_context(evaluator, petition_project, moulinette)


def ep_base_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    hedges_properties = reduce_hedges_properties_to_displayable_items(
        moulinette, petition_project
    )

    return {
        "hedges_properties": hedges_properties,
    }


def reduce_hedges_properties_to_displayable_items(moulinette, petition_project):

    hedges_properties = {}
    black_list = [
        "mode_plantation",
        "mode_destruction",
        "type_haie",
        "sur_parcelle_pac",
    ]
    hedge_to_plant_properties_form = import_string(
        moulinette.config.hedge_to_plant_properties_form
    )
    hedge_to_remove_properties_form = import_string(
        moulinette.config.hedge_to_remove_properties_form
    )
    for hedge in petition_project.hedge_data.hedges():
        form = (
            hedge_to_plant_properties_form
            if hedge.type == TO_PLANT
            else hedge_to_remove_properties_form
        )
        for key, field in form.base_fields.items():
            if key in black_list:
                continue

            is_choice = False

            if isinstance(field, ChoiceField):
                field_choices = [
                    (f"{key}.{choice[0]}", choice[1]) for choice in field.choices
                ]
                is_choice = True
            else:
                label = (
                    field.display_label
                    if isinstance(field, DisplayFieldMixin)
                    else field.label
                )
                field_choices = [(key, label)]

            for choice, label in field_choices:
                if choice not in hedges_properties:
                    hedges_properties[choice] = {
                        "label": label,
                        TO_REMOVE: (
                            HedgeList(label=label)
                            if key in hedge_to_remove_properties_form.base_fields
                            else None
                        ),
                        TO_PLANT: (
                            HedgeList(label=label)
                            if key in hedge_to_plant_properties_form.base_fields
                            else None
                        ),
                    }

            value = hedge.additionalData.get(key, None)
            if value:
                choice_key = f"{key}.{value}" if is_choice else key
                hedges_properties[choice_key][hedge.type].append(hedge)

    return hedges_properties
