import pytest
from django.contrib.sites.models import Site

from envergo.contrib.sites.tests.factories import SiteFactory
from envergo.evaluations.models import Evaluation, Request
from envergo.evaluations.tests.factories import EvaluationFactory, RequestFactory


@pytest.fixture
def evaluation() -> Evaluation:
    return EvaluationFactory()


@pytest.fixture
def legacy_eval() -> Evaluation:
    """Create an eval with the old data format.

    (criteria manually set, no moulinette_url)
    """
    return EvaluationFactory(moulinette_url="")


@pytest.fixture
def eval_request() -> Request:
    return RequestFactory()


@pytest.fixture(autouse=True)
def site() -> Site:
    return SiteFactory()
