from django.forms import ChoiceField
from django.utils.module_loading import import_string

from envergo.hedges.models import TO_PLANT, TO_REMOVE
from envergo.moulinette.forms.fields import DisplayFieldMixin
from envergo.moulinette.regulations.ep import (
    EspecesProtegeesAisne,
    EspecesProtegeesSimple,
)
from envergo.petitions.regulations import register_instructors_information
from envergo.petitions.services import (
    AdditionalInfo,
    InstructorInformation,
    Item,
    ItemDetails,
    Title,
)


def get_human_readable_value(field, key):
    for choice_key, human_readable in field.choices:
        if choice_key == key:
            return human_readable
    return None


@register_instructors_information(EspecesProtegeesAisne)
def ep_aisne_get_instructors_info(
    evaluator, petition_project, moulinette
) -> InstructorInformation:
    hedges_properties_items = reduce_hedges_properties_to_displayable_items(
        moulinette, petition_project
    )

    ep = InstructorInformation(
        slug="ep",
        label="Espèces protégées",
        key_elements=["onagre_number"],
        simulation_data=[
            Title("Calcul de la compensation attendue"),
            Item(
                "Coefficient compensation",
                float(evaluator.get_replantation_coefficient()),
                None,
                None,
            ),
            Title("Situation des haies"),
            *hedges_properties_items,
            Title("Liste des espèces"),
            "protected_species",
        ],
    )

    return ep


def reduce_hedges_properties_to_displayable_items(
    moulinette, petition_project
) -> list[Item]:

    # First create an intermediate data structure to aggregate the hedges properties
    hedges_properties = {}
    black_list = ["mode_plantation", "mode_destruction", "type_haie"]
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
                field_choices = [f"{key}.{choice[0]}" for choice in field.choices]
                is_choice = True
            else:
                field_choices = [key]

            for choice in field_choices:
                if choice not in hedges_properties:
                    hedges_properties[choice] = {
                        TO_REMOVE: (
                            []
                            if key in hedge_to_remove_properties_form.base_fields
                            else None
                        ),
                        TO_PLANT: (
                            []
                            if key in hedge_to_plant_properties_form.base_fields
                            else None
                        ),
                    }

            value = hedge.additionalData.get(key, None)
            if value:
                choice_key = f"{key}.{value}" if is_choice else key
                hedges_properties[choice_key][hedge.type].append(hedge)

    # Now create the displayable items
    hedges_properties_items = []
    for key, value in hedges_properties.items():
        choice = None
        if "." in key:
            splits = key.split(".")
            key = splits[0]
            choice = splits[1]

        field = (
            hedge_to_plant_properties_form.base_fields[key]
            if value[TO_PLANT] is not None
            else hedge_to_remove_properties_form.base_fields[key]
        )
        details = []

        label = (
            field.display_label
            if isinstance(field, DisplayFieldMixin)
            else (
                field.label
                if choice is None
                else get_human_readable_value(field, choice)
            )
        )

        if value[TO_REMOVE] is not None:
            details.append(
                AdditionalInfo(
                    label="Destruction",
                    value=get_hedges_length_and_names(value[TO_REMOVE]),
                    unit=None,
                )
            )
        if value[TO_PLANT] is not None:
            details.append(
                AdditionalInfo(
                    label="Plantation",
                    value=get_hedges_length_and_names(value[TO_PLANT]),
                    unit=None,
                )
            )

        hedges_properties_items.append(
            Item(
                label,
                ItemDetails(
                    result=value[TO_REMOVE] is not None
                    and len(value[TO_REMOVE]) > 0
                    or value[TO_PLANT] is not None
                    and len(value[TO_PLANT]) > 0,
                    details=details,
                ),
                None,
                None,
            )
        )
    return hedges_properties_items


def get_hedges_length_and_names(hedges):
    return f"{round(sum(h.length for h in hedges))} m " + (
        f" • {', '.join([h.id for h in hedges])}" if hedges else ""
    )


@register_instructors_information(EspecesProtegeesSimple)
def ep_simple_get_instructors_info(
    evaluator, petition_project, moulinette
) -> InstructorInformation:
    """Build Espèces Protégées informations for instructor page view"""

    hedge_data = petition_project.hedge_data

    hedges_to_remove_near_pond = [
        h for h in hedge_data.hedges_to_remove() if h.proximite_mare
    ]
    hedges_to_plant_near_pond = [
        h for h in hedge_data.hedges_to_plant() if h.proximite_mare
    ]

    hedges_to_remove_woodland_connection = [
        h for h in hedge_data.hedges_to_remove() if h.connexion_boisement
    ]
    hedges_to_plant_woodland_connection = [
        h for h in hedge_data.hedges_to_plant() if h.connexion_boisement
    ]

    hedges_to_plant_under_power_line = [
        h for h in hedge_data.hedges_to_plant() if h.sous_ligne_electrique
    ]

    ep = InstructorInformation(
        slug="ep",
        label="Espèces protégées",
        items=[
            "onagre_number",
            Item(
                "Présence d'une mare à moins de 200 m",
                ItemDetails(
                    result=len(hedges_to_remove_near_pond) > 0
                    or len(hedges_to_plant_near_pond) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_near_pond))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_remove_near_pond])}"
                                if hedges_to_remove_near_pond
                                else ""
                            ),
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_near_pond))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_plant_near_pond])}"
                                if hedges_to_plant_near_pond
                                else ""
                            ),
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
            Item(
                "Connexion à un boisement ou une haie",
                ItemDetails(
                    result=len(hedges_to_remove_woodland_connection) > 0
                    or len(hedges_to_plant_woodland_connection) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_woodland_connection))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_remove_woodland_connection])}"
                                if hedges_to_remove_woodland_connection
                                else ""
                            ),
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_woodland_connection))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_plant_woodland_connection])}"
                                if hedges_to_plant_woodland_connection
                                else ""
                            ),
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
            Item(
                "Proximité ligne électrique",
                ItemDetails(
                    result=len(hedges_to_plant_under_power_line) > 0,
                    details=[
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_under_power_line))} m "
                            + (
                                f" • {', '.join([h.id for h in hedges_to_plant_under_power_line])}"
                                if hedges_to_plant_under_power_line
                                else ""
                            ),
                            unit=None,
                        ),
                    ],
                ),
                None,
                None,
            ),
        ],
        details=[],
    )

    return ep
