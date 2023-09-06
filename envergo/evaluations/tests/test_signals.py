import pytest
from anymail.signals import tracking

from envergo.evaluations.models import MailLog
from envergo.evaluations.tests.factories import RegulatoryNoticeLogFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def event_data():
    # Copied from Brevo's doc
    return {
        "event": "opened",
        "email": "example@domain.com",
        "id": "webhook_id",
        "date": "2020-10-09 00:00:00",
        "ts": 1604933619,
        "message-id": "201798300811.5787683@relay.domain.com",
        "ts_event": 1604933654,
        "subject": "My first Transactional",
        "sending_ip": "xxx.xxx.xxx.xxx",
        "ts_epoch": 1604933654,
        "template_id": 22,
        "tags": ["transac_messages"],
    }


def test_webhook_event_catching(event_data):
    log_qs = MailLog.objects.all()
    assert log_qs.count() == 0

    message_id = "test_message_id"
    log = RegulatoryNoticeLogFactory(message_id=message_id)
    event_data["message-id"] = message_id

    tracking.send(sender=None, event=event_data, esp_name="sendinblue")
    assert log_qs.count() == 1

    log_event = log_qs[0]
    assert log_event.event == event_data["event"]
    assert log_event.recipient == event_data["email"]
    assert log_event.regulatory_notice_log == log
