import pytest

from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    PerimeterFactory,
    RegulationFactory,
)


@pytest.fixture()
def sites_classes_regulation():
    return RegulationFactory(regulation="sites_classes_haie", has_perimeters=True)


@pytest.fixture()
def sites_classes_perimeter(sites_classes_regulation, bizous_town_center):  # noqa
    return PerimeterFactory(
        name="Site classé de Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_classes_regulation],
    )


@pytest.fixture()
def sites_classes_criterion(
    sites_classes_regulation, sites_classes_perimeter, bizous_town_center  # noqa
):
    return CriterionFactory(
        title="Sites classés",
        regulation=sites_classes_regulation,
        perimeter=sites_classes_perimeter,
        evaluator="envergo.moulinette.regulations.sites_classes_haie.SitesClassesHaie",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )


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
        ),  # inside perimeter
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
        ),  # outside perimeter
    ],
)
def test_moulinette_evaluation(
    moulinette_data, expected_result, sites_classes_criterion
):
    DCConfigHaieFactory(regulations_available=["sites_classes_haie"])
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.sites_classes_haie.result == expected_result
    if expected_result != "non_concerne":
        assert (
            moulinette.sites_classes_haie.sites_classes_haie.result == expected_result
        )


@pytest.fixture
def moulinette_data_alignement_only(lat1, lng1, lat2, lng2):
    """Moulinette data with only alignement d'arbres hedges."""
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
                    "type_haie": "alignement",
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
    "lat1, lng1, lat2, lng2",
    [
        (
            43.06930871579473,
            0.4421436860179369,
            43.069162248282396,
            0.44236765047068033,
        ),  # inside perimeter
    ],
)
def test_aa_only_flag(moulinette_data_alignement_only, sites_classes_criterion):
    """Test that aa_only is True when all hedges are alignement d'arbres."""
    DCConfigHaieFactory(regulations_available=["sites_classes_haie"])
    moulinette = MoulinetteHaie(moulinette_data_alignement_only)
    assert moulinette.catalog.get("aa_only") is True


@pytest.mark.parametrize(
    "lat1, lng1, lat2, lng2",
    [
        (
            43.06930871579473,
            0.4421436860179369,
            43.069162248282396,
            0.44236765047068033,
        ),  # inside perimeter
    ],
)
def test_aa_only_false_with_mixed_hedges(moulinette_data, sites_classes_criterion):
    """Test that aa_only is False when hedges include non-alignement types."""
    DCConfigHaieFactory(regulations_available=["sites_classes_haie"])
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.catalog.get("aa_only") is False
