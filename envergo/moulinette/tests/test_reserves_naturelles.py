from math import ceil

import pytest

from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import make_hedge, make_moulinette_haie_data
from envergo.petitions.regulations import get_instructor_view_context

EVALUATOR_PATHS = (
    "envergo.moulinette.regulations.reserves_naturelles.ReservesNaturellesRu",
    "envergo.moulinette.regulations.reserves_naturelles.ReservesNaturellesHru",
    "envergo.moulinette.regulations.reserves_naturelles.ReservesNaturellesL3503",
)


@pytest.fixture(autouse=True)
def reserves_naturelles_criteria(bizous_town_center):  # noqa
    regulation = RegulationFactory(
        regulation="reserves_naturelles",
        has_perimeters=True,
        evaluator="envergo.moulinette.regulations.reserves_naturelles.ReservesNaturellesRegulation",
    )

    perimeter = PerimeterFactory(
        name="RN Bizous", activation_map=bizous_town_center, regulations=[regulation]
    )

    criteria = [
        CriterionFactory(
            title="Réserves Naturelles > RN Bizous",
            regulation=regulation,
            perimeter=perimeter,
            evaluator=evaluator_path,
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        )
        for evaluator_path in EVALUATOR_PATHS
    ]
    return criteria


@pytest.fixture
def moulinette_data(lat1, lng1, lat2, lng2, plan_gestion):
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": lat1, "lng": lng1},
                    {"lat": lat2, "lng": lng2},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "ripisylve": False,
                    "connexion_boisement": False,
                },
            }
        ]
    )
    data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "contexte": "non",
        "element": "haie",
        "department": "44",
        "plan_gestion": plan_gestion,
    }
    return {"initial": data, "data": data}


@pytest.mark.parametrize(
    "lat1, lng1, lat2, lng2, plan_gestion, expected_result, expected_lenght_resnat",
    [
        (
            43.06930871579473,
            0.4421436860179369,
            43.069162248282396,
            0.44236765047068033,
            "oui",
            "soumis_declaration",
            25,
        ),  # inside
        (
            43.069807900393826,
            0.4426179348420038,
            43.068048918563875,
            0.4415625648710002639653,
            "non",
            "soumis_autorisation",
            7,
        ),  # edge inside but vertices outside
        (
            43.09248072614743,
            0.48007431760217484,
            43.09280782621999,
            0.48095944654749073,
            "non",
            "non_concerne",
            None,
        ),  # outside
    ],
)
def test_moulinette_evaluation(
    moulinette_data, expected_result, expected_lenght_resnat
):
    DCConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.reserves_naturelles.result == expected_result

    if expected_result != "non_concerne":
        assert (
            moulinette.reserves_naturelles.hru__reserves_naturelles.result
            == expected_result
        )

        # The instructor view exposes each hedge with the length of its
        # intersection with the reserve's zones, instead of its full length.
        regulation_evaluator = moulinette.reserves_naturelles.get_evaluator()
        context = get_instructor_view_context(regulation_evaluator, None, moulinette)
        hedges = context["reserves_naturelles_hedges"]
        assert [h.id for h in hedges] == ["D1"]
        assert ceil(hedges[0].length) == expected_lenght_resnat


def test_hedges_to_plant_length_computed_independently_from_removal(
    bizous_town_center,  # noqa
):
    """The instructor view computes intersecting lengths for hedges to plant
    and hedges to remove independently: a hedge to plant inside the zone
    shows up even though the hedge to remove is entirely outside it.

    Also a regression test for ENVERGO-15B: when none of a perimeter's hedges
    intersect its zones, the zone aggregation returns None and must not crash.
    """

    # Hedge to plant inside the bizous zone (activates the criterion)
    # Hedge to remove well outside the zone (no zone intersection)
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "P1",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.06930871579473, "lng": 0.4421436860179369},
                    {"lat": 43.069162248282396, "lng": 0.44236765047068033},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                },
            },
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.10, "lng": 0.50},
                    {"lat": 43.11, "lng": 0.51},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "ripisylve": False,
                    "connexion_boisement": False,
                },
            },
        ]
    )
    data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "contexte": "non",
        "element": "haie",
        "department": "44",
        "plan_gestion": "non",
    }
    moulinette_data = {"initial": data, "data": data}

    DCConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)

    # Only the hedge to plant intersects a zone; the hedge to remove is
    # entirely absent (it doesn't intersect any zone at all).
    regulation_evaluator = moulinette.reserves_naturelles.get_evaluator()
    context = get_instructor_view_context(regulation_evaluator, None, moulinette)
    hedges = context["reserves_naturelles_hedges"]
    assert [h.id for h in hedges] == ["P1"]
    assert hedges[0].type == "TO_PLANT"
    assert ceil(hedges[0].length) == 25


EVALUATOR_CATEGORY_CASES = [
    ("ru", {"type_haie": "mixte"}),  # not an alignement => régime unique
    (
        "hru",
        {"type_haie": "alignement", "bord_voie": False},
    ),  # alignement outside road => hors régime unique
    (
        "l350_3",
        {"type_haie": "alignement", "bord_voie": True},
    ),  # roadside tree alignment => L350-3
]


@pytest.mark.parametrize("category, additional_data", EVALUATOR_CATEGORY_CASES)
def test_moulinette_evaluation_per_category(category, additional_data):
    """A hedge inside the reserve is assessed by the evaluator matching its category.

    The régime unique must be active for hedges to be routed by category at
    all: without it, every hedge is always assessed as "hru".
    """
    RUConfigHaieFactory()
    hedge = make_hedge(**additional_data)
    moulinette_data = make_moulinette_haie_data(hedge_data=[hedge], plan_gestion="oui")

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors
    regulation = moulinette.reserves_naturelles

    assert regulation.result == "soumis_declaration"
    # Only the matching category's criterion activates: the others have no
    # hedge in their category, so they never even run.
    assert (
        getattr(regulation, f"{category}__reserves_naturelles").result
        == "soumis_declaration"
    )


def test_procedure_type_only_depends_on_ru_category():
    """L350-3 and hru results must not influence the regulation procedure type.

    A hedge outside the régime unique is "soumis_autorisation" on its own
    criterion, but since it's not in the "ru" category, it doesn't bump the
    overall procedure to "autorisation": the régime unique category is
    "non_concerne" here, which maps to "declaration".
    """
    RUConfigHaieFactory()
    hedge = make_hedge(type_haie="alignement", bord_voie=False)
    moulinette_data = make_moulinette_haie_data(hedge_data=[hedge], plan_gestion="non")

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors
    regulation = moulinette.reserves_naturelles

    assert regulation.hru__reserves_naturelles.result == "soumis_autorisation"
    assert regulation.procedure_type == "declaration"
