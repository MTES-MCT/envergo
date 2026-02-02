import pytest

from envergo.geodata.conftest import (  # noqa
    bizous_town_center,
    france_map,
    loire_atlantique_map,
)
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture()
def sites_inscrits_regulation():
    return RegulationFactory(regulation="sites_inscrits_haie", has_perimeters=True)


@pytest.fixture()
def perimeter(sites_inscrits_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="SI Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_inscrits_regulation],
    )


@pytest.fixture()
def sites_inscrits_criteria(
    sites_inscrits_regulation, perimeter, bizous_town_center  # noqa
):

    criteria = [
        CriterionFactory(
            title="Sites inscrits",
            regulation=sites_inscrits_regulation,
            perimeter=perimeter,
            evaluator="envergo.moulinette.regulations.sites_inscrits_haie.SitesInscritsHaie",
            activation_map=bizous_town_center,
            activation_mode="hedges_intersection",
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data(lat1, lng1, lat2, lng2):
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
    }
    return {"initial": data, "data": data}


@pytest.mark.parametrize(
    "lat1, lng1, lat2, lng2, expected_result",
    [
        (
            43.06930871579473,
            0.4421436860179369,
            43.069162248282396,
            0.44236765047068033,
            "soumis",
        ),  # inside
        (
            43.069807900393826,
            0.4426179348420038,
            43.068048918563875,
            0.4415625648710002639653,
            "soumis",
        ),  # edge inside but vertices outside
        (
            43.09248072614743,
            0.48007431760217484,
            43.09280782621999,
            0.48095944654749073,
            "non_concerne",
        ),  # outside
    ],
)
def test_moulinette_evaluation(
    moulinette_data, expected_result, sites_inscrits_criteria
):
    DCConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.sites_inscrits_haie.result == expected_result
    if expected_result != "non_concerne":
        assert moulinette.sites_inscrits_haie.si_haie.result == expected_result
