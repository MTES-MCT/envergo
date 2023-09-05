import logging

from django.dispatch import Signal

try:
    from anymail.signals import tracking
except ModuleNotFoundError:
    tracking = Signal()

from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(tracking)
def handle_mail_event(sender, event, esp_name, **kwargs):
    logger.info(event, esp_name)
