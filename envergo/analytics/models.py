from django.contrib.sites.models import Site
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
    unique_id = models.CharField("ID unique", max_length=128, null=True, blank=True)

    # Add additional info to describe the event
    metadata = models.JSONField(_("Metadata"), null=True, blank=True)

    date_created = models.DateTimeField(_("Date created"), default=timezone.now)

    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
    )

    class Meta:
        verbose_name = _("Event")
        verbose_name_plural = _("Events")
        indexes = [
            models.Index(fields=["session_key"]),
            models.Index(fields=["category", "event"]),
        ]


class CSPReport(models.Model):
    """Stores a csp report event in db."""

    content = models.JSONField("Content", null=False)
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    session_key = models.CharField(_("Session key"), max_length=128)
    date_created = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = "CSP report"
        verbose_name_plural = "CSP reports"
