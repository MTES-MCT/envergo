import pytest

from envergo.analytics.models import Event
from envergo.analytics.utils import log_event

pytestmark = pytest.mark.django_db


def test_log_event(rf, user, admin_user):
    event_qs = Event.objects.all()
    assert event_qs.count() == 0

    request = rf.get("/")
    request.user = user
    request.COOKIES["visitorid"] = "1234"
    metadata = {"data1": "value1", "data2": "value2"}

    log_event("Category", "Event", request, **metadata)
    assert event_qs.count() == 1
    event = event_qs.first()
    assert event.category == "Category"
    assert event.event == "Event"
    assert event.metadata == metadata

    request.user = admin_user
    log_event("Category", "Event", request, **metadata)
    assert event_qs.count() == 1
