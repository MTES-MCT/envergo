from django.db import models
from django.utils.translation import ugettext_lazy as _


def evaluation_file_format(instance, filename):
    return f"evaluations/{instance.application_number}.pdf"


class Evaluation(models.Model):
    """A single evaluation for a building permit application."""

    application_number = models.CharField(_("Application number"), max_length=15)

    evaluation_file = models.FileField(
        _("Evaluation file"), upload_to=evaluation_file_format
    )

    class Meta:
        verbose_name = _("Evaluation")
        verbose_name_plural = _("Evaluations")
