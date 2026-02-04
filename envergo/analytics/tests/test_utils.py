from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser

from envergo.analytics.models import Event
from envergo.analytics.utils import get_hash_unique_id, is_request_from_a_bot, log_event

pytestmark = pytest.mark.django_db


def test_log_event(rf, user, haie_user, admin_user, site):
    event_qs = Event.objects.all()
    assert event_qs.count() == 0

    request = rf.get("/")
    request.user = user
    request.site = site
    request.COOKIES["visitorid"] = "1234"
    metadata = {"data1": "value1", "data2": "value2"}

    log_event("Category", "Event", request, **metadata)
    assert event_qs.count() == 1
    event = event_qs.first()
    assert event.category == "Category"
    assert event.event == "Event"
    assert event.metadata == metadata
    assert event.unique_id is None

    request.user = admin_user
    log_event("Category", "Event", request, **metadata)
    assert event_qs.count() == 1

    request.user = haie_user
    log_event("Category", "Event", request, **metadata)
    assert event_qs.count() == 2
    event = event_qs.last()
    assert event.unique_id == get_hash_unique_id(haie_user.email)

    request.user = AnonymousUser()
    log_event("Category", "Event", request, **metadata)
    assert event_qs.count() == 3
    event = event_qs.last()
    assert event.unique_id is None


def test_is_request_from_a_bot_no_ip(rf):
    """Returns False when no IP is provided."""
    request = rf.get("/")
    request.META.pop("HTTP_X_REAL_IP", None)
    assert is_request_from_a_bot(request) is False


def test_is_request_from_a_bot_invalid_ip(rf):
    """Returns False when IP is invalid (protects against injection)."""
    request = rf.get("/")
    request.META["HTTP_X_REAL_IP"] = "invalid\ninjection"
    assert is_request_from_a_bot(request) is False

    request.META["HTTP_X_REAL_IP"] = "not-an-ip"
    assert is_request_from_a_bot(request) is False


@patch("envergo.analytics.utils.socket.gethostbyaddr")
def test_is_request_from_a_bot_dns_error(mock_gethostbyaddr, rf):
    """Returns False when DNS lookup fails."""
    mock_gethostbyaddr.side_effect = OSError("DNS lookup failed")
    request = rf.get("/")
    request.META["HTTP_X_REAL_IP"] = "66.249.66.1"
    assert is_request_from_a_bot(request) is False


@patch("envergo.analytics.utils.socket.gethostbyaddr")
def test_is_request_from_a_bot_googlebot(mock_gethostbyaddr, rf):
    """Returns True for known bot domains."""
    mock_gethostbyaddr.return_value = ("crawl-66-249-66-1.googlebot.com", [], [])
    request = rf.get("/")
    request.META["HTTP_X_REAL_IP"] = "66.249.66.1"
    assert is_request_from_a_bot(request) is True


@patch("envergo.analytics.utils.socket.gethostbyaddr")
def test_is_request_from_a_bot_not_a_bot(mock_gethostbyaddr, rf):
    """Returns False for unknown domains."""
    mock_gethostbyaddr.return_value = ("some-random-host.example.com", [], [])
    request = rf.get("/")
    request.META["HTTP_X_REAL_IP"] = "192.168.1.1"
    assert is_request_from_a_bot(request) is False
