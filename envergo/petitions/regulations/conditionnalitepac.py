from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.regulations.conditionnalitepac import Bcae8
from envergo.petitions.regulations import register_instructors_information
from envergo.petitions.services import GroupedItems, InstructorInformation, Item


@register_instructors_information(Bcae8)
def bcae8_get_instructors_info(
    evaluator, petition_project, moulinette
) -> InstructorInformation:
    """Build BCAE8 for instructor page view"""

    hedge_data = petition_project.hedge_data
    lineaire_detruit_pac = hedge_data.lineaire_detruit_pac()
    lineaire_to_plant_pac = hedge_data.length_to_plant_pac()
    lineaire_total = moulinette.catalog.get("lineaire_total", "")
    motif = moulinette.catalog.get("motif", "")

    bcae8 = InstructorInformation(
        slug="bcae8",
        comment="Les décomptes de cette section n'incluent que les haies déclarées "
        "sur parcelle PAC. Les alignements d’arbres sont également exclus.",
        label="BCAE 8",
        items=[
            Item("Total linéaire exploitation déclaré", lineaire_total, "m", None),
            Item(
                "Motif",
                next((v[1] for v in MOTIF_CHOICES if v[0] == motif), motif),
                None,
                None,
            ),
        ],
        details=[],
    )

    if lineaire_detruit_pac:
        bcae8.details.append(
            GroupedItems(
                label="Destruction",
                items=[
                    Item(
                        "Total linéaire à détruire sur parcelle PAC",
                        round(hedge_data.lineaire_detruit_pac()),
                        "m",
                        None,
                    ),
                    Item(
                        "Détail",
                        (
                            ", ".join(
                                [
                                    f"{round(h.length)} m ⋅ {h.id}"
                                    for h in hedge_data.hedges_to_remove_pac()
                                ]
                            )
                            if hedge_data.hedges_to_remove_pac
                            else ""
                        ),
                        None,
                        None,
                    ),
                    Item(
                        "Pourcentage linéaire à détruire / total linéaire exploitation",
                        (
                            round(lineaire_detruit_pac / lineaire_total * 100, 2)
                            if lineaire_total
                            else ""
                        ),
                        "%",
                        None,
                    ),
                ],
            )
        )
    else:
        bcae8.details.append(
            GroupedItems(
                label="Destruction",
                items=[
                    Item(
                        "Total linéaire détruit sur parcelle PAC",
                        round(hedge_data.lineaire_detruit_pac()),
                        "m",
                        None,
                    ),
                ],
            )
        )

    if lineaire_to_plant_pac:
        bcae8.details.append(
            GroupedItems(
                label="Plantation",
                items=[
                    Item(
                        "Total linéaire à planter sur parcelle PAC",
                        round(lineaire_to_plant_pac),
                        "m",
                        None,
                    ),
                    Item(
                        "Détail",
                        (
                            ", ".join(
                                [
                                    f"{round(h.length)} m ⋅ {h.id}"
                                    for h in hedge_data.hedges_to_plant_pac()
                                ]
                            )
                            if hedge_data.hedges_to_plant_pac
                            else ""
                        ),
                        None,
                        None,
                    ),
                    Item(
                        "Ratio de replantation",
                        (
                            round(
                                lineaire_to_plant_pac / lineaire_detruit_pac,
                                2,
                            )
                            if lineaire_detruit_pac > 0
                            else ""
                        ),
                        None,
                        "Linéaire à planter / linéaire à détruire, sur parcelle PAC",
                    ),
                ],
            ),
        )
    else:
        bcae8.details.append(
            GroupedItems(
                label="Plantation",
                items=[
                    Item(
                        "Total linéaire à planter sur parcelle PAC",
                        round(lineaire_to_plant_pac),
                        "m",
                        None,
                    ),
                ],
            )
        )

    return bcae8
