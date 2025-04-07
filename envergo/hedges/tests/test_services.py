from unittest.mock import Mock, patch

import pytest

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.services import HedgeEvaluator, PlantationEvaluator
from envergo.moulinette.tests.factories import CriterionFactory, RegulationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def ep_criterion(france_map):  # noqa
    criterion = CriterionFactory(
        title="Espèces protégées",
        regulation=RegulationFactory(regulation="ep"),
        evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesAisne",
        activation_map=france_map,
    )
    return criterion


@patch("envergo.hedges.services.get_replantation_coefficient")
def test_minimum_length_to_plant(mock_get_R):
    """Length to plant deponds on the replantation coefficient."""

    moulinette = Mock()

    hedge_data = Mock()
    hedge_data.hedges_to_remove.return_value = []
    hedge_data.length_to_remove.return_value = 100

    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0

    hedge_data.lineaire_detruit_pac.return_value = 0
    hedge_data.length_to_plant_pac.return_value = 0

    mock_get_R.return_value = 2.0
    evaluator = PlantationEvaluator(moulinette, hedge_data)
    assert evaluator.minimum_length_to_plant() == 200

    mock_get_R.return_value = 4.0
    assert evaluator.minimum_length_to_plant() == 400


@patch("envergo.hedges.services.get_replantation_coefficient")
def test_minimum_lengths_to_plant(mock_get_R, hedge_data):

    moulinette = Mock()

    mock_get_R.return_value = 2.0
    evaluator = PlantationEvaluator(moulinette, hedge_data)
    minimum_lengths_to_plant = evaluator.get_minimum_lengths_to_plant()

    assert round(minimum_lengths_to_plant["degradee"]) == 2 * 50
    assert round(minimum_lengths_to_plant["buissonnante"]) == 2 * 40
    assert round(minimum_lengths_to_plant["arbustive"]) == 2 * 30
    assert round(minimum_lengths_to_plant["mixte"]) == 2 * 20
    assert round(minimum_lengths_to_plant["alignement"]) == 2 * 10

    mock_get_R.return_value = 4.0
    minimum_lengths_to_plant = evaluator.get_minimum_lengths_to_plant()
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

    plantation_evaluator = Mock()
    plantation_evaluator.hedge_data = hedge_data
    plantation_evaluator.minimum_length_to_plant.return_value = 0
    plantation_evaluator.get_minimum_lengths_to_plant.return_value = {
        "degradee": 12,
        "buissonnante": 12,
        "arbustive": 16,
        "mixte": 18,
        "alignement": 20,
    }
    plantation_evaluator.get_lengths_to_plant.return_value = {
        "buissonnante": 24,
        "arbustive": 16,
        "mixte": 18,
        "alignement": 20,
    }

    # plantation_evaluator = PlantationEvaluator(moulinette, hedge_data)
    evaluator = HedgeEvaluator(plantation_evaluator)

    assert evaluator.evaluate_hedge_plantation_quality() == {
        "result": True,
        "missing_plantation": {
            "mixte": 0,
            "alignement": 0,
            "arbustive": 0,
            "buissonante": 0,
            "degradee": 0,
        },
    }


def test_hedge_quality_should_not_be_sufficient():
    hedge_data = Mock()
    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0
    hedge_data.length_to_plant_pac.return_value = 5
    hedge_data.lineaire_detruit_pac.return_value = 10

    plantation_evaluator = Mock()
    plantation_evaluator.hedge_data = hedge_data
    plantation_evaluator.minimum_length_to_plant.return_value = 0
    plantation_evaluator.get_minimum_lengths_to_plant.return_value = {
        "degradee": 10,
        "buissonnante": 10,
        "arbustive": 10,
        "mixte": 10,
        "alignement": 10,
    }
    plantation_evaluator.get_lengths_to_plant.return_value = {
        "buissonnante": 5,
        "arbustive": 5,
        "mixte": 5,
        "alignement": 5,
    }

    evaluator = HedgeEvaluator(plantation_evaluator)

    assert evaluator.evaluate_hedge_plantation_quality() == {
        "result": False,
        "missing_plantation": {
            "mixte": 5,
            "alignement": 5,
            "arbustive": 5,
            "buissonante": 5,
            "degradee": 10,
        },
    }


def test_hedge_quality_evaluation():
    # given not enough hedges to plant
    hedge_data = Mock()
    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 10
    hedge_data.length_to_plant_pac.return_value = 5
    hedge_data.lineaire_detruit_pac.return_value = 10

    plantation_evaluator = Mock()
    plantation_evaluator.hedge_data = hedge_data
    plantation_evaluator.minimum_length_to_plant.return_value = 90
    plantation_evaluator.get_minimum_lengths_to_plant.return_value = {
        "degradee": 10,
        "buissonnante": 10,
        "arbustive": 10,
        "mixte": 10,
        "alignement": 10,
    }
    plantation_evaluator.get_lengths_to_plant.return_value = {
        "buissonnante": 5,
        "arbustive": 5,
        "mixte": 5,
        "alignement": 5,
    }

    # when evaluating the hedge quality
    evaluator = HedgeEvaluator(plantation_evaluator)

    # then the left_to_plant should be positive
    assert evaluator.result == {
        "do_not_plant_under_power_line": {"result": True},
        "length_to_plant": {
            "left_to_plant": 80,
            "minimum_length_to_plant": 90,
            "result": False,
        },
        "length_to_plant_pac": {
            "left_to_plant": 5,
            "minimum_length_to_plant": 10,
            "result": False,
        },
        "quality": {
            "missing_plantation": {
                "alignement": 5,
                "arbustive": 5,
                "buissonante": 5,
                "degradee": 10,
                "mixte": 5,
            },
            "result": False,
        },
    }

    # given enough hedges to plant
    hedge_data.length_to_plant.return_value = 100
    hedge_data.length_to_plant_pac.return_value = 100
    hedge_data.lineaire_detruit_pac.return_value = 90
    plantation_evaluator.minimum_length_to_plant.return_value = 90

    # when evaluating the hedge quality
    evaluator = HedgeEvaluator(plantation_evaluator)

    # then the left_to_plant should be 0
    assert evaluator.result == {
        "do_not_plant_under_power_line": {"result": True},
        "length_to_plant": {
            "left_to_plant": 0,
            "minimum_length_to_plant": 90,
            "result": True,
        },
        "length_to_plant_pac": {
            "left_to_plant": 0,
            "minimum_length_to_plant": 90,
            "result": True,
        },
        "quality": {
            "missing_plantation": {
                "alignement": 5,
                "arbustive": 5,
                "buissonante": 5,
                "degradee": 10,
                "mixte": 5,
            },
            "result": False,
        },
    }
