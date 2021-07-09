import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def evaluation_file_format(instance, filename):
    return f"evaluations/{instance.application_number}.pdf"


class Evaluation(models.Model):
    """A single evaluation for a building permit application."""

    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_number = models.CharField(_("Application number"), max_length=15)
    evaluation_file = models.FileField(
        _("Evaluation file"),
        upload_to=evaluation_file_format,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Evaluation")
        verbose_name_plural = _("Evaluations")

    def __str__(self):
        return self.application_number
