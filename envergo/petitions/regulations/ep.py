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


@register_instructors_information(EspecesProtegeesAisne)
def ep_aisne_get_instructors_info(evaluator, petition_project, moulinette):
    return [Title(label="EP Aisne")]


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

    if (
        moulinette
        and hasattr(moulinette, "ep")
        and moulinette.ep
        and moulinette.ep._evaluator
        and callable(
            getattr(moulinette.ep._evaluator, "get_instructor_informations", None)
        )
    ):
        compensation_items = [Title("Calcul de la compensation attendue")].extend(
            moulinette.ep._evaluator.get_compensation_instructor_informations()
        )
    else:
        compensation_items = []

    ep = InstructorInformation(
        slug="ep",
        label="Espèces protégées",
        items=[
            *compensation_items,
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
