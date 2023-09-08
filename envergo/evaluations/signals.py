import logging

from anymail.signals import tracking
from django.db.models import F
from django.dispatch import receiver

from envergo.evaluations.models import MailLog, RecipientStatus, RegulatoryNoticeLog

logger = logging.getLogger(__name__)


# Those are the only events we want to track
# Note: those events name are normalized by anymail
# See https://anymail.dev/en/stable/sending/tracking/#event-tracking
TRACKED_EVENTS = ("opened", "clicked")


@receiver(tracking)
def handle_mail_event(sender, event, esp_name, **kwargs):
    event_name = event.event_type
    recipient = event.recipient
    message_id = event.message_id
    timestamp = event.timestamp

    logger.info(f"Received event {event.event_type} for message id {message_id}")
    try:
        regulatory_notice_log = RegulatoryNoticeLog.objects.get(message_id=message_id)
    except RegulatoryNoticeLog.DoesNotExist:
        logger.warning(f"Could not find message id {message_id}")
        return

    logger.info(
        f"Received event {event_name} for {recipient} on notice {regulatory_notice_log.pk}"
    )
    MailLog.objects.create(
        regulatory_notice_log=regulatory_notice_log,
        event=event_name,
        date=timestamp,
        recipient=recipient,
    )

    status = RecipientStatus.objects.get_or_create(
        regulatory_notice_log=regulatory_notice_log,
        recipient=recipient,
        defaults={"status": event_name, "latest_status": timestamp},
    )
    if status.latest_status < timestamp:
        status.status = event_name
        status.latest_status = timestamp

    if event_name == "opened":
        status.nb_opened = F("nb_opened") + 1
        status.latest_opened = timestamp
    elif event_name == "clicked":
        status.nb_clicked = F("nb_clicked") + 1
        status.latest_clicked = timestamp

    status.save()
