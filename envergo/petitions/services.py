from dataclasses import dataclass


@dataclass
class AdditionalInfo:
    label: str
    value: str | int | float
    unit: str | None


@dataclass
class ItemDetails:
    result: bool
    details: list[AdditionalInfo]


@dataclass
class Item:
    label: str
    value: str | int | float | ItemDetails
    unit: str | None
    comment: str | None


@dataclass
class InstructorInformationDetails:
    label: str
    items: list[Item]


@dataclass
class InstructorInformation:
    slug: str | None
    label: str | None
    items: list[Item]
    details: list[InstructorInformationDetails]


def compute_instructor_informations(
    petition_project, moulinette
) -> list[InstructorInformation]:
    hedge_data = petition_project.hedge_data
    length_to_remove = hedge_data.length_to_remove()
    length_to_plant = hedge_data.length_to_plant()
    project_details = InstructorInformation(
        slug=None,
        label=None,
        items=[
            Item("Référence", petition_project.reference, None, None),
        ],
        details=[
            InstructorInformationDetails(
                label="Destruction",
                items=[
                    Item(
                        "Nombre de tracés",
                        len(hedge_data.hedges_to_remove()),
                        None,
                        None,
                    ),
                    Item("Total linéaire détruit", length_to_remove, "m", None),
                ],
            ),
            InstructorInformationDetails(
                label="Plantation",
                items=[
                    Item(
                        "Nombre de tracés",
                        len(hedge_data.hedges_to_plant()),
                        None,
                        None,
                    ),
                    Item("Total linéaire planté", length_to_plant, "m", None),
                    Item(
                        "Ratio en longueur",
                        (
                            round(length_to_plant / length_to_remove, 2)
                            if length_to_remove
                            else ""
                        ),
                        None,
                        "longueur plantée / longueur détruite",
                    ),
                ],
            ),
        ],
    )

    lineaire_total = moulinette.catalog.get("lineaire_total", "")
    lineaire_detruit_pac = hedge_data.lineaire_detruit_pac()
    lineaire_plante_pac = hedge_data.lineaire_plante_pac()

    bcae8 = InstructorInformation(
        slug="bcae8",
        label="BCAE 8",
        items=[
            Item("Total linéaire exploitation déclaré", lineaire_total, "m", None),
            Item("Motif", moulinette.catalog.get("motif", ""), None, None),
        ],
        details=[
            InstructorInformationDetails(
                label="Destruction",
                items=[
                    Item(
                        "Nombre de tracés sur parcelle PAC",
                        len(hedge_data.hedges_to_remove_pac()),
                        None,
                        None,
                    ),
                    Item(
                        "Total linéaire détruit hors alignement d’arbres",
                        hedge_data.lineaire_detruit_pac(),
                        "m",
                        "Sur parcelle PAC, hors alignement d’arbres",
                    ),
                    Item(
                        "Pourcentage détruit / total linéaire",
                        (
                            round(lineaire_detruit_pac / lineaire_total * 100, 2)
                            if lineaire_total
                            else ""
                        ),
                        "%",
                        None,
                    ),
                ],
            ),
            InstructorInformationDetails(
                label="Plantation",
                items=[
                    Item(
                        "Nombre de tracés plantés hors alignement d’arbres",
                        len(hedge_data.hedges_to_plant_pac()),
                        None,
                        None,
                    ),
                    Item(
                        "Total linéaire planté",
                        hedge_data.lineaire_plante_pac(),
                        "m",
                        "Hors alignement d’arbres",
                    ),
                    Item(
                        "Ratio en longueur",
                        (
                            round(lineaire_plante_pac / lineaire_detruit_pac, 2)
                            if lineaire_detruit_pac > 0
                            else ""
                        ),
                        None,
                        "Longueur plantée / longueur détruite (prises hors alignements d’arbres)",
                    ),
                ],
            ),
        ],
    )

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

    hedges_to_remove_under_power_line = [
        h for h in hedge_data.hedges_to_remove() if h.sous_ligne_electrique
    ]
    hedges_to_plant_under_power_line = [
        h for h in hedge_data.hedges_to_plant() if h.sous_ligne_electrique
    ]
    ep = InstructorInformation(
        slug="ep",
        label="Espèces protégées",
        items=[
            Item(
                "Présence d'une mare à moins de 200 m",
                ItemDetails(
                    result=len(hedges_to_remove_near_pond) > 0
                    or len(hedges_to_plant_near_pond) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_near_pond))} m "
                            f"• {', '.join([h.id for h in hedges_to_remove_near_pond])}",
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_near_pond))} m "
                            f"• {', '.join([h.id for h in hedges_to_plant_near_pond])}",
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
                            f"• {', '.join([h.id for h in hedges_to_remove_woodland_connection])}",
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_woodland_connection))} m "
                            f"• {', '.join([h.id for h in hedges_to_plant_woodland_connection])}",
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
                    result=len(hedges_to_remove_under_power_line) > 0
                    or len(hedges_to_plant_under_power_line) > 0,
                    details=[
                        AdditionalInfo(
                            label="Destruction",
                            value=f"{round(sum(h.length for h in hedges_to_remove_under_power_line))} m "
                            f"• {', '.join([h.id for h in hedges_to_remove_under_power_line])}",
                            unit=None,
                        ),
                        AdditionalInfo(
                            label="Plantation",
                            value=f"{round(sum(h.length for h in hedges_to_plant_under_power_line))} m "
                            f"• {', '.join([h.id for h in hedges_to_plant_under_power_line])}",
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

    return [project_details, bcae8, ep]
