import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils.choices import Choices

from envergo.evaluations.validators import application_number_validator
from envergo.utils.markdown import markdown_to_html


def evaluation_file_format(instance, filename):
    return f"evaluations/{instance.application_number}.pdf"


PROBABILITIES = Choices(
    (1, "unlikely", _("Unlikely")),
    (2, "possible", _("Possible")),
    (3, "likely", _("Likely")),
    (4, "likely+", _("Very likely")),
)


class Evaluation(models.Model):
    """A single evaluation for a building permit application."""

    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_number = models.CharField(
        _("Application number"),
        max_length=15,
        unique=True,
        db_index=True,
        validators=[application_number_validator],
    )
    evaluation_file = models.FileField(
        _("Evaluation file"),
        upload_to=evaluation_file_format,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )

    commune = models.CharField(
        _("Commune"),
        max_length=256,
        help_text=_("The name and postcode of the project commune"),
    )
    created_surface = models.IntegerField(
        _("Created surface"), help_text=_("In square meters")
    )
    existing_surface = models.IntegerField(
        _("Existing surface"), null=True, blank=True, help_text=_("In square meters")
    )
    global_probability = models.IntegerField(_("Probability"), choices=PROBABILITIES)
    rainwater_runoff_probability = models.IntegerField(
        _("Rainwater runoff probability"), choices=PROBABILITIES
    )
    rainwater_runoff_impact = models.TextField(_("Rainwater runoff impact"))
    flood_zone_probability = models.IntegerField(
        _("Flood zone probability"), choices=PROBABILITIES
    )
    flood_zone_impact = models.TextField(_("Flood zone impact"))
    wetland_probability = models.IntegerField(
        _("Wetland probability"), choices=PROBABILITIES
    )
    wetland_impact = models.TextField(_("Wetland impact"))
    contact_md = models.TextField(_("Contact"), blank=True)
    contact_html = models.TextField(_("Contact (html)"), blank=True)

    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Evaluation")
        verbose_name_plural = _("Evaluations")

    def __str__(self):
        return self.application_number

    def save(self, *args, **kwargs):
        self.contact_html = markdown_to_html(self.contact_md)
        super().save(*args, **kwargs)

    @property
    def application_number_display(self):
        an = self.application_number
        # Those are non-breaking spaces
        return f"{an[0:2]} {an[2:5]} {an[5:8]} {an[8:10]} {an[10:]}"


CRITERIONS = Choices(
    ("rainwater_runoff", _("Capture of more than 1 ha of rainwater runoff")),
    ("flood_zone", _("Building of more than 400 m¹ in a flood zone")),
    ("wetland", _("More than 1000 m² impact on wetlands")),
)


class Criterion(models.Model):
    """A single evaluation item."""

    evaluation = models.ForeignKey(
        "Evaluation",
        on_delete=models.CASCADE,
        verbose_name=_("Evaluation"),
        related_name="criterions",
    )
    order = models.PositiveIntegerField(_("Order"), default=0)
    probability = models.IntegerField(_("Probability"), choices=PROBABILITIES)
    criterion = models.CharField(_("Criterion"), max_length=128, choices=CRITERIONS)
    description_md = models.TextField(_("Description"))
    description_html = models.TextField(_("Description (html)"))
    map = models.ImageField(_("Map"), null=True, blank=True)
    legend_md = models.CharField(_("Legend"), max_length=256, blank=True)
    legend_html = models.TextField(_("Legend (html)"), blank=True)

    class Meta:
        verbose_name = _("Criterion")
        verbose_name_plural = _("Criterions")
        unique_together = [("evaluation", "criterion")]

    def __str__(self):
        return self.get_criterion_display()

    def save(self, *args, **kwargs):
        self.description_html = markdown_to_html(self.description_md)
        self.legend_html = markdown_to_html(self.legend_md)
        super().save(*args, **kwargs)

    def get_law_code(self):
        """Return the water law code describing this criterion."""

        return {
            "rainwater_runoff": "2.1.5.0",
            "flood_zone": "3.2.2.0",
            "wetland": "3.3.1.0",
        }.get(self.criterion)
