import pytest
from anymail.signals import AnymailTrackingEvent, tracking
from django.utils import timezone

from envergo.evaluations.models import RecipientStatus
from envergo.evaluations.tests.factories import RegulatoryNoticeLogFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def event():
    data = {
        "event_type": "opened",
        "recipient": "example@domain.com",
        "message_id": "test_message_id",
        "timestamp": timezone.now(),
    }
    event = AnymailTrackingEvent(**data)
    return event


def test_webhook_event_catching(event):
    event["event_type"] = "unique_opened"
    statuses_qs = RecipientStatus.objects.all()
    assert statuses_qs.count() == 0

    log = RegulatoryNoticeLogFactory(message_id="test_message_id")
    tracking.send(sender=None, event=event, esp_name="sendinblue")
    assert statuses_qs.count() == 1

    log_event = statuses_qs[0]
    assert log_event.recipient == event.recipient
    assert log_event.regulatory_notice_log == log
    assert log_event.nb_opened == 1
    assert not log_event.on_error

    event["event_type"] = "opened"
    tracking.send(sender=None, event=event, esp_name="sendinblue")
    tracking.send(sender=None, event=event, esp_name="sendinblue")
    log_event.refresh_from_db()
    assert log_event.nb_opened == 3


def test_webhook_error_catching(event, mailoutbox):
    assert len(mailoutbox) == 0

    event.event_type = "hard_bounce"

    statuses_qs = RecipientStatus.objects.all()
    assert statuses_qs.count() == 0

    log = RegulatoryNoticeLogFactory(message_id="test_message_id")
    tracking.send(sender=None, event=event, esp_name="sendinblue")
    assert statuses_qs.count() == 1

    log_event = statuses_qs[0]
    assert log_event.recipient == event.recipient
    assert log_event.regulatory_notice_log == log
    assert log_event.on_error
    assert len(mailoutbox) == 1

    mail = mailoutbox[0]
    assert mail.subject == "Erreur d'envoi d'AR à example@domain.com"
    assert "Un avis réglementaire n'a pas pu être délivré" in mail.body
