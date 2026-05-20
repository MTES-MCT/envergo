import logging

from anymail.signals import tracking
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from envergo.evaluations.models import Evaluation, RegulatoryNoticeLog
from envergo.evaluations.tasks import (
    post_evaluation_to_automation,
    warn_admin_of_email_error,
)

logger = logging.getLogger(__name__)

# Those are the events we want to receive from the ESP and track
# There is also an order of priority, and the latest status in not
# necessarily the one we want to keep
# E.g if a message is already "clicked", and later the recipient
# opens it again and we receive an "opened" event, we want the status
# to stay "clicked"
TRACKED_EVENTS = ["queued", "delivered", "opened", "clicked"]

# Those are the events that mean the message was not delivered
ERROR_EVENTS = [
    "deferred",
    "rejected",
    "bounced",
    "failed",
]


@receiver(tracking)
def handle_mail_event(sender, event, esp_name, **kwargs):
    """Handle error events received from Brevo.

    The events we are trackinrg are related to the evaluations emails ("avis réglementaires").
    We only track errors.
    """
    event_name = event.event_type
    recipient = event.recipient
    message_id = event.message_id
    timestamp = event.timestamp
    reject_reason = event.reject_reason

    if event_name not in ERROR_EVENTS:
        return

    try:
        regulatory_notice_log = RegulatoryNoticeLog.objects.get(message_id=message_id)
    except RegulatoryNoticeLog.DoesNotExist:
        logger.warning(f"Could not find message id {message_id}")
        return

    logger.info(
        f"Received event {event_name} for {recipient} on notice {regulatory_notice_log.pk}"
    )
    error_status = {
        "recipient": recipient,
        "timestamp": timestamp,
        "error_type": event_name,
        "reject_reason": reject_reason or "",
    }
    warn_admin_of_email_error.delay(regulatory_notice_log.id, error_status)


@receiver(post_save, sender=Evaluation)
def handle_evaluation_edition(sender, instance, **kwargs):
    if not kwargs.get("created", False):
        transaction.on_commit(lambda: post_evaluation_to_automation.delay(instance.uid))
