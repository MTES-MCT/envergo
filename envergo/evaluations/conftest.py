import pytest

from envergo.evaluations.models import Evaluation
from envergo.evaluations.tests.factories import EvaluationFactory


@pytest.fixture
def evaluation() -> Evaluation:
    return EvaluationFactory()
