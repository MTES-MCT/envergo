from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class ResultSnapshotBase(models.Model):
    """Abstract base class for result snapshots.

    This stores a snapshot of moulinette results at a specific point in time.
    Subclasses should add a ForeignKey to the relevant model (e.g., PetitionProject, Evaluation).
    """

    payload = models.JSONField(encoder=DjangoJSONEncoder)
    moulinette_url = models.URLField(_("Moulinette url"), max_length=2048)
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        abstract = True
