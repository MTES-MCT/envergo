from django.template.defaultfilters import floatformat
from django.utils.module_loading import import_string

from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.forms.fields import DisplayFieldMixin
from envergo.moulinette.regulations.conditionnalitepac import Bcae8, Bcae8Form
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

    hedge_to_plant_properties_form = import_string(
        moulinette.config.hedge_to_plant_properties_form
    )

    has_mode_replantation = (
        "mode_replantation" in hedge_to_plant_properties_form.base_fields
    )

    bcae8 = InstructorInformation(
        slug="bcae8",
        comment="Les décomptes de cette section n'incluent que les haies déclarées "
        "sur parcelle PAC. Les alignements d’arbres sont également exclus.",
        label="BCAE 8",
        key_elements=[
            Item(
                "Motif",
                next((v[1] for v in MOTIF_CHOICES if v[0] == motif), motif),
                None,
                None,
            ),
        ],
        simulation_data=[
            Item(
                "Total linéaire exploitation déclaré",
                floatformat(lineaire_total, "0g"),
                "m",
                None,
            ),
        ],
    )

    for key in Bcae8Form.base_fields:
        if key in moulinette.catalog and key != "lineaire_total":
            field = Bcae8Form.base_fields[key]
            label = (
                field.display_label
                if isinstance(field, DisplayFieldMixin)
                else field.label
            )
            unit = field.display_unit if isinstance(field, DisplayFieldMixin) else None
            bcae8.simulation_data.append(
                Item(label, moulinette.catalog[key], unit, None)
            )

    if lineaire_detruit_pac:
        bcae8.key_elements.append(
            GroupedItems(
                label="Destruction",
                items=[
                    Item(
                        "Total linéaire à détruire sur parcelle PAC",
                        floatformat(lineaire_detruit_pac, "0g"),
                        "m",
                        None,
                    ),
                    Item(
                        "Détail",
                        (
                            ", ".join(
                                [
                                    f"{floatformat(h.length, "0g")} m ⋅ {h.id}"
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
                            floatformat(
                                lineaire_detruit_pac / lineaire_total * 100, "2g"
                            )
                            if lineaire_total
                            else ""
                        ),
                        "%",
                        None,
                    ),
                ],
            )
        )

    if lineaire_to_plant_pac:
        bcae8.key_elements.append(
            GroupedItems(
                label="Plantation",
                items=[
                    Item(
                        "Total linéaire à planter sur parcelle PAC",
                        floatformat(lineaire_to_plant_pac, "0g"),
                        "m",
                        None,
                    ),
                    Item(
                        "Détail",
                        (
                            ", ".join(
                                [
                                    f"{floatformat(h.length, "0g")} m ⋅ {h.id}"
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
                            floatformat(
                                lineaire_to_plant_pac / lineaire_detruit_pac,
                                "2g",
                            )
                            if lineaire_detruit_pac > 0
                            else ""
                        ),
                        None,
                        (
                            "Linéaire plantation nouvelle ou remplacement / linéaire à détruire, sur parcelle PAC"
                            if has_mode_replantation
                            else "Linéaire à planter / linéaire à détruire, sur parcelle PAC"
                        ),
                    ),
                ],
            ),
        )

    return bcae8
