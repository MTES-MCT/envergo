from unittest.mock import Mock

import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.regulations import (
    CriterionBasedMinLengthCondition,
    MinLengthCondition,
    MinLengthPacCondition,
    QualityCondition,
    SafetyCondition,
)

pytestmark = pytest.mark.django_db


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


def test_criterion_based_minimum_length_condition():
    """Length to plant depends on a criterion custom computation."""

    hedge_data = Mock()
    hedge_data.hedges_to_remove.return_value = []
    hedge_data.length_to_remove.return_value = 100

    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0

    condition = CriterionBasedMinLengthCondition(
        hedge_data, 2.0, **{"minimum_length_to_plant": 200}
    )
    condition.evaluate()
    assert condition.context["minimum_length_to_plant"] == 200

    condition = CriterionBasedMinLengthCondition(
        hedge_data, 4.0, **{"minimum_length_to_plant": 200}
    )
    condition.evaluate()
    assert condition.context["minimum_length_to_plant"] == 200


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
