from unittest.mock import Mock

import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.regulations import (
    MinLengthCondition,
    MinLengthPacCondition,
    QualityCondition,
    SafetyCondition,
    StrenghteningCondition,
)
from envergo.hedges.tests.factories import HedgeDataFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def calvados_hedge_data():
    hedge_data = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "mode_destruction": "arrachage",
                    "type_haie": "degradee",
                    "position": "interchamp",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
                },
            },
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.694364, "lng": 3.615415},
                    {"lat": 43.694094, "lng": 3.615085},
                ],
                "additionalData": {
                    "mode_destruction": "arrachage",
                    "type_haie": "degradee",
                    "position": "interchamp",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
                },
            },
            {
                "id": "D3",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.694347, "lng": 3.615455},
                    {"lat": 43.694144, "lng": 3.615210},
                ],
                "additionalData": {
                    "mode_destruction": "arrachage",
                    "type_haie": "degradee",
                    "position": "interchamp",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
                },
            },
            {
                "id": "P1",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "mode_plantation": "plantation",
                    "type_haie": "alignement",
                    "essences_non_bocageres": False,
                    "sur_parcelle_pac": False,
                    "position": "interchamp",
                    "proximite_mare": False,
                    "sous_ligne_electrique": False,
                    "sur_talus": False,
                },
            },
            {
                "id": "P2",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.694376, "lng": 3.615381},
                    {"lat": 43.694050, "lng": 3.614952},
                ],
                "additionalData": {
                    "mode_plantation": "plantation",
                    "type_haie": "alignement",
                    "essences_non_bocageres": False,
                    "sur_parcelle_pac": False,
                    "position": "interchamp",
                    "proximite_mare": False,
                    "sous_ligne_electrique": False,
                    "sur_talus": False,
                },
            },
        ]
    )
    return hedge_data


def test_minimum_length_condition():
    """Length to plant depends on the replantation coefficient."""

    hedge_data = Mock()
    hedge_data.hedges_to_remove.return_value = []
    hedge_data.length_to_remove.return_value = 100

    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0

    hedge_data.lineaire_detruit_pac.return_value = 0
    hedge_data.length_to_plant_pac.return_value = 0

    condition = MinLengthCondition(hedge_data, 2.0)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant"] == 200

    condition = MinLengthCondition(hedge_data, 4.0)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant"] == 400


def test_minimum_length_pac_condition():
    """Length to plant on pac does not depends on R."""

    hedge_data = Mock()
    hedge_data.hedges_to_remove.return_value = []
    hedge_data.length_to_remove.return_value = 100

    hedge_data.hedges_to_plant_pac.return_value = []
    hedge_data.length_to_plant_pac.return_value = 0

    hedge_data.lineaire_detruit_pac.return_value = 100
    hedge_data.length_to_plant_pac.return_value = 0

    condition = MinLengthPacCondition(hedge_data, 2.0)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant_pac"] == 100

    condition = MinLengthPacCondition(hedge_data, 4.0)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant_pac"] == 100

    condition = MinLengthPacCondition(hedge_data, 0.0)
    condition.evaluate()
    assert condition.context["minimum_length_to_plant_pac"] == 0


def test_safety_condition(hedge_data):
    """Planting under power lines is not ok."""

    condition = SafetyCondition(hedge_data, 1.0)
    condition.evaluate()
    assert condition.result

    hedge_data.data[-1]["additionalData"].update(
        {
            "type_haie": "alignement",
            "sous_ligne_electrique": True,
        }
    )
    condition = SafetyCondition(hedge_data, 1.0)
    condition.evaluate()
    assert not condition.result


def test_quality_condition_lengths_to_plant(hedge_data):
    """Lengths to plant depends on R."""

    condition = QualityCondition(hedge_data, 2.0)
    minimum_lengths_to_plant = condition.get_minimum_lengths_to_plant()
    assert round(minimum_lengths_to_plant["degradee"]) == 2 * 50
    assert round(minimum_lengths_to_plant["buissonnante"]) == 2 * 40
    assert round(minimum_lengths_to_plant["arbustive"]) == 2 * 30
    assert round(minimum_lengths_to_plant["mixte"]) == 2 * 20
    assert round(minimum_lengths_to_plant["alignement"]) == 2 * 10

    condition = QualityCondition(hedge_data, 4.0)
    minimum_lengths_to_plant = condition.get_minimum_lengths_to_plant()
    assert round(minimum_lengths_to_plant["degradee"]) == 4 * 50
    assert round(minimum_lengths_to_plant["buissonnante"]) == 4 * 40
    assert round(minimum_lengths_to_plant["arbustive"]) == 4 * 30
    assert round(minimum_lengths_to_plant["mixte"]) == 4 * 20
    assert round(minimum_lengths_to_plant["alignement"]) == 4 * 10


def test_hedge_quality_should_be_sufficient():
    hedge_data = Mock()
    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0
    hedge_data.lineaire_detruit_pac.return_value = 10
    hedge_data.length_to_plant_pac.return_value = 5

    condition = QualityCondition(hedge_data, 2.0)
    condition.get_minimum_lengths_to_plant = Mock(
        return_value={
            "degradee": 12,
            "buissonnante": 12,
            "arbustive": 16,
            "mixte": 18,
            "alignement": 20,
        }
    )
    condition.get_lengths_to_plant = Mock(
        return_value={
            "buissonnante": 24,
            "arbustive": 16,
            "mixte": 18,
            "alignement": 20,
        }
    )
    condition.evaluate()

    assert condition.result
    assert condition.context["missing_plantation"] == {
        "mixte": 0,
        "alignement": 0,
        "arbustive": 0,
        "buissonante": 0,
        "degradee": 0,
    }


def test_hedge_quality_should_not_be_sufficient():
    hedge_data = Mock()
    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0
    hedge_data.length_to_plant_pac.return_value = 5
    hedge_data.lineaire_detruit_pac.return_value = 10

    condition = QualityCondition(hedge_data, 2.0)
    condition.get_minimum_lengths_to_plant = Mock(
        return_value={
            "degradee": 10,
            "buissonnante": 10,
            "arbustive": 10,
            "mixte": 10,
            "alignement": 10,
        }
    )
    condition.get_lengths_to_plant = Mock(
        return_value={
            "buissonnante": 5,
            "arbustive": 5,
            "mixte": 5,
            "alignement": 5,
        }
    )
    condition.evaluate()
    assert not condition.result
    assert condition.context["missing_plantation"] == {
        "mixte": 5,
        "alignement": 5,
        "arbustive": 5,
        "buissonante": 5,
        "degradee": 10,
    }


def test_strengthening_condition(calvados_hedge_data):
    hedge_data = calvados_hedge_data
    catalog = {"reimplantation": "replantation"}

    condition = StrenghteningCondition(hedge_data, 1.0, catalog)
    condition.evaluate()
    assert condition.result
    assert condition.context["strengthening_length"] == 0.0
    assert condition.context["strengthening_excess"] < 0.0

    hedge_data.data[-1]["additionalData"]["mode_plantation"] = "renforcement"
    hedge_data.data[-2]["additionalData"]["mode_plantation"] = "reconnexion"

    condition = StrenghteningCondition(hedge_data, 1.0, catalog)
    condition.evaluate()
    assert not condition.result
    assert condition.context["length_to_plant"] == 100.0
    assert condition.context["length_to_remove"] == 120.0
    assert condition.context["strengthening_max"] == 24.0  # 120 * 0.2
    assert condition.context["strengthening_length"] == 100.0
    assert condition.context["strengthening_excess"] == 76.0
