import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from envergo.petitions.models import StatusLog

logger = logging.getLogger(__name__)


@receiver(post_save, sender=StatusLog)
def on_status_log_save(sender, instance, created, **kwargs):
    if not created:
        # trigger the task only if on creation
        return

    instance.petition_project.update_status(instance)
