import logging
from datetime import datetime

from anymail.signals import tracking
from django.dispatch import receiver

from envergo.evaluations.models import MailLog, RegulatoryNoticeLog

logger = logging.getLogger(__name__)


@receiver(tracking)
def handle_mail_event(sender, event, esp_name, **kwargs):
    event_name = event["event"]
    recipient = event["email"]
    timestamp = event["ts"]
    message_id = event["message-id"]
    subject = event["subject"]
    date = datetime.fromtimestamp(timestamp)

    try:
        regulatory_notice_log = RegulatoryNoticeLog.objects.get(message_id=message_id)
    except RegulatoryNoticeLog.DoesNotExist:
        return

    logger.info(
        f"Received event {event_name} for {recipient} on notice {regulatory_notice_log.pk}"
    )
    MailLog.objects.create(
        regulatory_notice_log=regulatory_notice_log,
        event=event_name,
        date=date,
        recipient=recipient,
        subject=subject,
    )
