import pytest

from envergo.geodata.conftest import bizous_town_center  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def reserves_naturelles_criteria(bizous_town_center):  # noqa
    regulation = RegulationFactory(
        regulation="reserves_naturelles", has_perimeters=True
    )

    perimeter = PerimeterFactory(
        name="RN Bizous", activation_map=bizous_town_center, regulations=[regulation]
    )

    criteria = [
        CriterionFactory(
            title="Réserves Naturelles > RN Bizous",
            regulation=regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.reserves_naturelles.ReservesNaturelles",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        ),
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
                    "proximite_point_eau": False,
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
    ConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.reserves_naturelles.result == expected_result

    if expected_result != "non_concerne":
        assert (
            moulinette.reserves_naturelles.reserves_naturelles.result == expected_result
        )
        assert moulinette.catalog["l_resnat"] == expected_lenght_resnat
