from django.forms import ChoiceField
from django.utils.module_loading import import_string

from envergo.hedges.models import TO_PLANT, TO_REMOVE, HedgeList
from envergo.hedges.regulations import NormandieQualityCondition
from envergo.moulinette.forms.fields import DisplayFieldMixin
from envergo.moulinette.regulations.ep import (
    EspecesProtegeesAisne,
    EspecesProtegeesNormandie,
    EspecesProtegeesRegimeUnique,
    EspecesProtegeesSimple,
)
from envergo.petitions.regulations import (
    evaluator_instructor_view_context_getter,
    get_line_buffer_density_context,
)


@evaluator_instructor_view_context_getter(EspecesProtegeesNormandie)
def ep_normandie_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    context = ep_base_get_instructor_view_context(
        evaluator, petition_project, moulinette
    )
    R = evaluator.get_replantation_coefficient()
    hedge_data = moulinette.catalog.get("haies")
    context["quality_condition"] = (
        NormandieQualityCondition(hedge_data, R, evaluator, catalog=moulinette.catalog)
        .evaluate()
        .context
    )
    context["replantation_coefficient"] = R

    # swap Mixte and alignement for a specific table display
    ordered_hedge_types = list(reversed(moulinette.hedge_types))
    values = [choice.value for choice in ordered_hedge_types]
    if "mixte" in values and "alignement" in values:
        i, j = values.index("mixte"), values.index("alignement")
        ordered_hedge_types[i], ordered_hedge_types[j] = (
            ordered_hedge_types[j],
            ordered_hedge_types[i],
        )
    context["ordered_hedge_types"] = ordered_hedge_types

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


@evaluator_instructor_view_context_getter(EspecesProtegeesRegimeUnique)
def ep_regime_unique_get_instructor_view_context(
    evaluator, petition_project, moulinette
) -> dict:
    """Build density + EP régime unique parameters for the instructor view."""
    context = ep_base_get_instructor_view_context(
        evaluator, petition_project, moulinette
    )
    context.update(get_line_buffer_density_context(petition_project, moulinette))

    context["ep_ru_total_length"] = moulinette.catalog.get("ep_ru_total_length")
    context["ep_ru_ripisylve_length"] = moulinette.catalog.get("ep_ru_ripisylve_length")
    context["replantation_coefficient"] = evaluator.get_replantation_coefficient()
    context["ep_ru_hedge_rows"] = evaluator.build_hedge_rows()

    return context


def reduce_hedges_properties_to_displayable_items(moulinette, petition_project):
    """Reduce heges properties grouped by property
    Without properties black listed
    Ordered by forms fieldset
    """

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

    # Order keys according to fieldsets order in form without black listed keys
    ordered_fields_keys = []
    for values in hedge_to_remove_properties_form.fieldsets.values():
        for value in values:
            if value in black_list:
                continue
            ordered_fields_keys.append(value)
    for values in hedge_to_plant_properties_form.fieldsets.values():
        for value in values:
            if value in black_list:
                continue
            if value in ordered_fields_keys:
                continue
            ordered_fields_keys.append(value)

    # Start hedges list with a TO_REMOVE hedge
    hedges = petition_project.hedge_data.hedges()
    hedges.sort(key=lambda h: h.type, reverse=True)

    for hedge in hedges:
        form = (
            hedge_to_plant_properties_form
            if hedge.type == TO_PLANT
            else hedge_to_remove_properties_form
        )

        # Create list of hedges properties
        for key in ordered_fields_keys:

            if key not in form.base_fields:
                continue

            field = form.base_fields[key]
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
