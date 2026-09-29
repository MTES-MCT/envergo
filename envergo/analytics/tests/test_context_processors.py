import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
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
    assert context == {"matomo_dimensions": [(1, "n3_d0"), (2, "n0_d0")]}


def test_few_evalreq_events(req):
    EvalreqEventFactory.create_batch(5, session_key=VISITOR_ID)
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n2_d0"), (2, "n0_d0")]}


def test_single_evalreq_recent_event(req):
    EvalreqEventFactory(
        session_key=VISITOR_ID,
        date_created=timezone.now() - timezone.timedelta(days=20),
    )
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n1_d1"), (2, "n0_d0")]}


def test_single_evalreq_not_long_ago_event(req):
    EvalreqEventFactory(
        session_key=VISITOR_ID,
        date_created=timezone.now() - timezone.timedelta(days=50),
    )
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n1_d2"), (2, "n0_d0")]}


def test_single_evalreq_old_event(req):
    EvalreqEventFactory(
        session_key=VISITOR_ID,
        date_created=timezone.now() - timezone.timedelta(days=70),
    )
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n1_d3"), (2, "n0_d0")]}


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


def test_even_more_simulation_events(req):
    SimulationEventFactory.create_batch(60, session_key=VISITOR_ID)
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n4_d0")]}


def test_single_simulation_recent_event(req):
    SimulationEventFactory(
        session_key=VISITOR_ID,
        date_created=timezone.now() - timezone.timedelta(days=20),
    )
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n1_d1")]}


def test_single_simulation_not_so_recent_event(req):
    SimulationEventFactory(
        session_key=VISITOR_ID,
        date_created=timezone.now() - timezone.timedelta(days=50),
    )
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n1_d2")]}


def test_single_simulation_old_event(req):
    SimulationEventFactory(
        session_key=VISITOR_ID,
        date_created=timezone.now() - timezone.timedelta(days=61),
    )
    context = analytics(req)
    assert context == {"matomo_dimensions": [(1, "n0_d0"), (2, "n1_d3")]}


@pytest.fixture
def haie_req(rf, site):
    site.domain = settings.ENVERGO_HAIE_DOMAIN
    request = rf.get("/")
    request.site = site
    return request


def test_haie_anonymous_user_type(haie_req):
    haie_req.user = AnonymousUser()
    context = analytics(haie_req)
    assert context == {"matomo_dimensions": [(1, "anonymous")]}


def test_haie_administrator_user_type(haie_req, admin_user):
    haie_req.user = admin_user
    context = analytics(haie_req)
    assert context == {"matomo_dimensions": [(1, "administrator")]}


def test_haie_coordinator_user_type(haie_req, haie_coordinator_44):
    haie_req.user = haie_coordinator_44
    context = analytics(haie_req)
    assert context == {"matomo_dimensions": [(1, "coordinator")]}


def test_haie_instructor_user_type(haie_req, haie_user_44):
    haie_req.user = haie_user_44
    context = analytics(haie_req)
    assert context == {"matomo_dimensions": [(1, "instructor")]}


def test_haie_guest_user_type(haie_req, amenagement_user):
    haie_req.user = amenagement_user
    context = analytics(haie_req)
    assert context == {"matomo_dimensions": [(1, "guest")]}
