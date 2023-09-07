import logging

from anymail.signals import tracking
from django.db.models import F
from django.dispatch import receiver

from envergo.evaluations.models import MailLog, RegulatoryNoticeLog

logger = logging.getLogger(__name__)


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

    if event_name == "opened":
        regulatory_notice_log.nb_opened = F("nb_opened") + 1
        regulatory_notice_log.last_opened = timestamp
        regulatory_notice_log.save()
    elif event_name == "clicked":
        regulatory_notice_log.nb_clicked = F("nb_clicked") + 1
        regulatory_notice_log.last_clicked = timestamp
        regulatory_notice_log.save()
