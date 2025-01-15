from unittest.mock import Mock

import pytest

from envergo.hedges.services import HedgeEvaluator

pytestmark = pytest.mark.django_db


def test_hedge_quality_should_be_sufficient():
    hedge_data = Mock()
    hedge_data.hedges_to_plant.return_value = []
    hedge_data.length_to_plant.return_value = 0
    hedge_data.minimum_length_to_plant.return_value = 0
    hedge_data.get_minimum_lengths_to_plant.return_value = {
        "degradee": 12,
        "buissonnante": 12,
        "arbustive": 16,
        "mixte": 18,
        "alignement": 20,
    }
    hedge_data.get_lengths_to_plant.return_value = {
        "buissonnante": 24,
        "arbustive": 16,
        "mixte": 18,
        "alignement": 20,
    }

    evaluator = HedgeEvaluator(hedge_data=hedge_data)

    assert evaluator.evaluate_hedge_plantation_quality() == {
        "code": "quality",
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
    hedge_data.minimum_length_to_plant.return_value = 0
    hedge_data.get_minimum_lengths_to_plant.return_value = {
        "degradee": 10,
        "buissonnante": 10,
        "arbustive": 10,
        "mixte": 10,
        "alignement": 10,
    }
    hedge_data.get_lengths_to_plant.return_value = {
        "buissonnante": 5,
        "arbustive": 5,
        "mixte": 5,
        "alignement": 5,
    }

    evaluator = HedgeEvaluator(hedge_data=hedge_data)

    assert evaluator.evaluate_hedge_plantation_quality() == {
        "code": "quality",
        "result": False,
        "missing_plantation": {
            "mixte": 5,
            "alignement": 5,
            "arbustive": 5,
            "buissonante": 5,
            "degradee": 10,
        },
    }
