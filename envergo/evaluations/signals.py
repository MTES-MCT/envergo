import logging

from anymail.signals import tracking
from django.db.models import F
from django.dispatch import receiver

from envergo.evaluations.models import RecipientStatus, RegulatoryNoticeLog

logger = logging.getLogger(__name__)

# Those are the events we want to receive fro mthe ESP and track
# There is also an order of priority, and the latest status in not
# necessarily the one we want to keep
# E.g if a message is already "clicked", and later the recipient
# opens it again and we receive an "opened" event, we want the status
# to stay "clicked"
TRACKED_EVENTS = ["sent", "delivered", "opened", "clicked"]


@receiver(tracking)
def handle_mail_event(sender, event, esp_name, **kwargs):
    event_name = event.event_type
    recipient = event.recipient
    message_id = event.message_id
    timestamp = event.timestamp

    logger.info(f"Received event {event.event_type} for message id {message_id}")
    if event_name not in TRACKED_EVENTS:
        return

    try:
        regulatory_notice_log = RegulatoryNoticeLog.objects.get(message_id=message_id)
    except RegulatoryNoticeLog.DoesNotExist:
        logger.warning(f"Could not find message id {message_id}")
        return

    logger.info(
        f"Received event {event_name} for {recipient} on notice {regulatory_notice_log.pk}"
    )
    status, _created = RecipientStatus.objects.get_or_create(
        regulatory_notice_log=regulatory_notice_log,
        recipient=recipient,
        defaults={"status": event_name, "latest_status": timestamp},
    )

    status_index = TRACKED_EVENTS.index(event_name)
    latest_status_index = TRACKED_EVENTS.index(status.latest_status)
    if status_index > latest_status_index:
        status.status = event_name
        status.latest_status = timestamp

    if event_name == "opened":
        status.nb_opened = F("nb_opened") + 1
        status.latest_opened = timestamp
    elif event_name == "clicked":
        status.nb_clicked = F("nb_clicked") + 1
        status.latest_clicked = timestamp

    status.save()
