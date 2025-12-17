import factory
import pytest

from envergo.geodata.conftest import (  # noqa
    bizous_town_center,
    france_map,
    loire_atlantique_map,
)
from envergo.geodata.tests.factories import Department34Factory
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
def sites_proteges_regulation():
    return RegulationFactory(regulation="sites_proteges_haie", has_perimeters=True)


@pytest.fixture()
def mh_perimeter(sites_proteges_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="MH Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_proteges_regulation],
    )


@pytest.fixture()
def spr_perimeter(sites_proteges_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="SPR Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_proteges_regulation],
    )


@pytest.fixture()
def sites_proteges_criteria(
    sites_proteges_regulation, spr_perimeter, mh_perimeter, bizous_town_center  # noqa
):

    criteria = [
        CriterionFactory(
            title="Sites Patrimoniaux Remarquables",
            regulation=sites_proteges_regulation,
            perimeter=spr_perimeter,
            evaluator="envergo.moulinette.regulations.sites_proteges_haie.SitesPatrimoniauxRemarquablesHaie",
            activation_map=bizous_town_center,
            activation_mode="all_hedges_intersection",
        ),
        CriterionFactory(
            title="Monuments historiques",
            regulation=sites_proteges_regulation,
            perimeter=mh_perimeter,
            evaluator="envergo.moulinette.regulations.sites_proteges_haie.MonumentsHistoriquesHaie",
            activation_map=bizous_town_center,
            activation_mode="all_hedges_intersection",
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
    moulinette_data, expected_result, sites_proteges_criteria
):
    DCConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.sites_proteges_haie.result == expected_result
    if expected_result != "non_concerne":
        assert moulinette.sites_proteges_haie.mh_haie.result == expected_result
        assert moulinette.sites_proteges_haie.spr_haie.result == expected_result


def test_moulinette_evaluation_activation_mode(
    sites_proteges_regulation, spr_perimeter, mh_perimeter, bizous_town_center  # noqa
):
    # GIVEN a moulinette with an hedge to plant inside the MH and SPR perimeter, and an hedge to remove outside
    DCConfigHaieFactory()

    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.09248072614743, "lng": 0.48007431760217484},
                    {"lat": 43.09280782621999, "lng": 0.48095944654749073},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "proximite_point_eau": False,
                    "connexion_boisement": False,
                },
            },
            {
                "id": "P1",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.069807900393826, "lng": 0.4426179348420038},
                    {"lat": 43.068048918563875, "lng": 0.4415625648710002639653},
                ],
                "additionalData": {
                    "type_haie": "mixte",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "proximite_point_eau": False,
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
        "element": "haie",
        "department": "44",
    }
    moulinette_data = {"initial": data, "data": data}

    # GIVEN the MH criteria with activation mode all_hedges_intersection
    # and the SPR criteria with activation mode hedges_intersection
    CriterionFactory(
        title="Sites Patrimoniaux Remarquables",
        regulation=sites_proteges_regulation,
        perimeter=spr_perimeter,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.SitesPatrimoniauxRemarquablesHaie",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )
    CriterionFactory(
        title="Monuments historiques",
        regulation=sites_proteges_regulation,
        perimeter=mh_perimeter,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.MonumentsHistoriquesHaie",
        activation_map=bizous_town_center,
        activation_mode="all_hedges_intersection",
    ),

    # WHEN evaluating the moulinette
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the result is soumis for MH criteria but not evaluated for SPR
    assert moulinette.sites_proteges_haie.mh_haie.result == "soumis"
    assert not hasattr(moulinette.sites_proteges_haie, "spr_haie")


def test_moulinette_evaluation_department_centroid(
    sites_proteges_regulation, loire_atlantique_map, france_map  # noqa
):
    # GIVEN a moulinette in Loire Atlantique
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.09248072614743, "lng": 0.48007431760217484},
                    {"lat": 43.09280782621999, "lng": 0.48095944654749073},
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
    moulinette_data = {"initial": data, "data": data}

    # GIVEN criteria with activation mode department_centroid and a perimeter covering Loire Atlantique
    la_perimeter = PerimeterFactory(
        name="SPR 44",
        activation_map=loire_atlantique_map,
        regulations=[sites_proteges_regulation],
    )
    CriterionFactory(
        title="Sites Patrimoniaux Remarquables",
        regulation=sites_proteges_regulation,
        perimeter=la_perimeter,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.SitesPatrimoniauxRemarquablesHaie",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    CriterionFactory(
        title="Monuments historiques",
        regulation=sites_proteges_regulation,
        perimeter=la_perimeter,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.MonumentsHistoriquesHaie",
        activation_map=france_map,
        activation_mode="department_centroid",
    ),

    # WHEN evaluating the moulinette
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the result is soumis for both criteria
    assert moulinette.sites_proteges_haie.result == "soumis"
    assert moulinette.sites_proteges_haie.mh_haie.result == "soumis"
    assert moulinette.sites_proteges_haie.spr_haie.result == "soumis"

    # GIVEN a moulinette in Herault
    DCConfigHaieFactory(department=factory.SubFactory(Department34Factory))
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.09248072614743, "lng": 0.48007431760217484},
                    {"lat": 43.09280782621999, "lng": 0.48095944654749073},
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
        "department": "34",
    }
    moulinette_data = {"initial": data, "data": data}

    # WHEN evaluating the moulinette
    moulinette = MoulinetteHaie(moulinette_data)

    # THEN the result is non_concerne even if criteria are soumis
    assert moulinette.sites_proteges_haie.result == "non_concerne"
    assert moulinette.sites_proteges_haie.mh_haie.result == "soumis"
    assert moulinette.sites_proteges_haie.spr_haie.result == "soumis"
