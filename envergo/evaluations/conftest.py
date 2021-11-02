import pytest

from envergo.evaluations.models import Evaluation, Request
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory


@pytest.fixture
def evaluation() -> Evaluation:
    return EvaluationFactory()


@pytest.fixture
def eval_request() -> Request:
    return RequestFactory()
