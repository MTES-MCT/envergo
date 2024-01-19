from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Event(models.Model):
    """Stores an event in db for analytics purpose."""

    # Category and event describe an event we want to track
    # e.g "simulateur -> soumission" or "évaluation -> demande".
    category = models.CharField(_("Category"), max_length=128)
    event = models.CharField(_("Event"), max_length=128)

    # Connect several events by the same user
    session_key = models.CharField(_("Session key"), max_length=128)

    # Add additional info to describe the event
    metadata = models.JSONField(_("Metadata"), null=True, blank=True)

    date_created = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Event")
        verbose_name_plural = _("Events")
        indexes = [
            models.Index(fields=["session_key"]),
            models.Index(fields=["category", "event"]),
        ]
