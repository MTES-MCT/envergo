import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


@pytest.fixture(autouse=True)
def regime_unique_haie_criteria(request, france_map):  # noqa
    regulation = RegulationFactory(
        regulation="regime_unique_haie",
        evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaieRegulation",
    )
    if request.node.get_closest_marker("disable_regime_haie_criterion"):
        return

    criteria = [
        CriterionFactory(
            title="Regime unique haie",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.regime_unique_haie.RegimeUniqueHaie",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    return criteria


@pytest.fixture
def moulinette_data(type_haie):
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.0693, "lng": 0.4421},
                    {"lat": 43.0695, "lng": 0.4420},
                ],
                "additionalData": {
                    "type_haie": type_haie,
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
    "type_haie, expected_result, expected_result_code",
    [
        (
            "mixte",
            "soumis",
            "soumis",
        ),
        (
            "alignement",
            "non_concerne",
            "non_concerne_aa",
        ),
    ],
)
def test_moulinette_evaluation_single_procedure(
    moulinette_data, expected_result, expected_result_code
):
    RUConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.regime_unique_haie.result == expected_result
    assert (
        moulinette.regime_unique_haie.regime_unique_haie.result_code
        == expected_result_code
    )


@pytest.mark.parametrize(
    "type_haie, expected_result, expected_result_code",
    [
        ("mixte", "non_concerne", "non_concerne"),
        ("alignement", "non_concerne", "non_concerne"),
    ],
)
def test_moulinette_evaluation_droit_constant(
    moulinette_data, expected_result, expected_result_code
):
    DCConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.regime_unique_haie.result == expected_result
    assert (
        moulinette.regime_unique_haie.regime_unique_haie.result_code
        == expected_result_code
    )


@pytest.mark.parametrize(
    "type_haie, expected_result",
    [("mixte", "non_active"), ("alignement", "non_active")],
)
def test_moulinette_evaluation_non_active(moulinette_data, expected_result):
    RUConfigHaieFactory(regulations_available=[])
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.regime_unique_haie.result == expected_result


@pytest.mark.parametrize(
    "type_haie, expected_result",
    [("mixte", "non_disponible"), ("alignement", "non_disponible")],
)
@pytest.mark.disable_regime_haie_criterion
def test_moulinette_evaluation_non_disponible(moulinette_data, expected_result):
    RUConfigHaieFactory()
    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.regime_unique_haie.result == expected_result
