import pytest
from django.conf import settings
from django.utils import timezone

from envergo.analytics.context_processors import analytics
from envergo.analytics.tests.factories import (
    EvalreqEventFactory,
    SimulationEventFactory,
)

pytestmark = pytest.mark.django_db


VISITOR_ID = "gloubiboulga"


@pytest.fixture
def req(rf):
    request = rf.get("/")
    request.COOKIES[settings.VISITOR_COOKIE_NAME] = VISITOR_ID
    return request


def test_analytics_with_no_data_and_no_cookie(req):
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n0_d0")]}


def test_single_evalreq_event(req):
    EvalreqEventFactory(session_key=VISITOR_ID)
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n1_d0"), (2, "n0_d0")]}


def test_several_evalreq_events(req):
    EvalreqEventFactory.create_batch(15, session_key=VISITOR_ID)
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n2_d0"), (2, "n0_d0")]}


def test_single_evalreq_old_event(req):
    EvalreqEventFactory(
        session_key=VISITOR_ID,
        date_created=timezone.now() - timezone.timedelta(days=61),
    )
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n1_d1"), (2, "n0_d0")]}


def test_single_simulation_event(req):
    SimulationEventFactory(session_key=VISITOR_ID)
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n1_d0")]}


def test_several_simulation_events(req):
    SimulationEventFactory.create_batch(5, session_key=VISITOR_ID)
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n2_d0")]}


def test_more_simulation_events(req):
    SimulationEventFactory.create_batch(15, session_key=VISITOR_ID)
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n3_d0")]}


def test_single_simulation_old_event(req):
    SimulationEventFactory(
        session_key=VISITOR_ID,
        date_created=timezone.now() - timezone.timedelta(days=61),
    )
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n1_d1")]}
