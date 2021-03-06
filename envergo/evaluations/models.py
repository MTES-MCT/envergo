import secrets
import uuid
from os.path import splitext

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.files.storage import get_storage_class
from django.core.validators import FileExtensionValidator
from django.db import models
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from model_utils.choices import Choices
from phonenumber_field.modelfields import PhoneNumberField

from envergo.evaluations.validators import application_number_validator
from envergo.utils.markdown import markdown_to_html


def evaluation_file_format(instance, filename):
    return f"evaluations/{instance.application_number}.pdf"


def generate_reference():
    """Generate a short random and readable reference."""

    # letters and numbers without 1, i, O, 0, etc.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    length = settings.ENVERGO_REFERENCE_LENGTH

    # Since the volume of evaluation is quite low, we just hope that we
    # won't randomly get a profanity
    reference = "".join(secrets.choice(alphabet) for i in range(length))

    return reference


PROBABILITIES = Choices(
    (1, "unlikely", _("Unlikely")),
    (2, "possible", _("Possible")),
    (3, "likely", _("Likely")),
    (4, "very_likely", _("Very likely")),
)


RESULTS = Choices(
    ("soumis", "Soumis"),
    ("non_soumis", "Non soumis"),
    ("action_requise", "Action requise"),
    ("non_disponible", "Non disponible"),
    ("non_applicable", "Non concernĂ©"),
)


class Evaluation(models.Model):
    """A single evaluation for a building permit application."""

    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(
        _("Reference"),
        max_length=64,
        default=generate_reference,
        unique=True,
        db_index=True,
    )
    contact_email = models.EmailField(_("E-mail"))
    request = models.OneToOneField(
        "evaluations.Request",
        verbose_name=_("Request"),
        help_text=_("Does this evaluation answers to an existing request?"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    application_number = models.CharField(
        _("Application number"),
        max_length=15,
        validators=[application_number_validator],
        blank=True,
    )
    evaluation_file = models.FileField(
        _("Evaluation file"),
        upload_to=evaluation_file_format,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )

    address = models.TextField(_("Address"))
    created_surface = models.IntegerField(
        _("Created surface"), help_text=_("In square meters")
    )
    existing_surface = models.IntegerField(
        _("Existing surface"), null=True, blank=True, help_text=_("In square meters")
    )
    result = models.CharField(_("Result"), max_length=32, choices=RESULTS, null=True)
    details_md = models.TextField(_("Details"), blank=True)
    details_html = models.TextField(_("Details"), blank=True)
    contact_md = models.TextField(_("Contact"), blank=False)
    contact_html = models.TextField(_("Contact (html)"), blank=True)

    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Evaluation")
        verbose_name_plural = _("Evaluations")

    def __str__(self):
        return self.reference

    def get_absolute_url(self):
        return reverse("evaluation_detail", args=[self.reference])

    def save(self, *args, **kwargs):
        self.contact_html = markdown_to_html(self.contact_md)
        self.details_html = markdown_to_html(self.details_md)
        super().save(*args, **kwargs)

    def compute_result(self):
        """Compute evaluation result depending on eval criterions."""

        results = [criterion.result for criterion in self.criterions.all()]

        if CRITERION_RESULTS.soumis in results:
            result = RESULTS.soumis
        elif CRITERION_RESULTS.action_requise in results:
            result = RESULTS.action_requise
        else:
            result = RESULTS.non_soumis
        return result

    @property
    def application_number_display(self):
        an = self.application_number
        # Those are non-breaking spaces
        return f"{an[0:2]}Â {an[2:5]}Â {an[5:8]}Â {an[8:10]}Â {an[10:]}"


CRITERIONS = Choices(
    (
        "rainwater_runoff",
        "<strong>Impact sur l'Ă©coulement des eaux pluviales</strong><br /> Seuil de dĂ©clarationÂ : 1Â ha",
    ),
    (
        "flood_zone",
        "<strong>Impact sur une zone inondable</strong><br /> Seuil de dĂ©clarationÂ : 400Â mÂ²",
    ),
    (
        "wetland",
        "<strong>Impact sur une zone humide</strong><br /> Seuil de dĂ©clarationÂ : 1Â 000Â mÂ²",
    ),
)


ACTIONS = Choices(
    ("surface_lt_1000", "n'impacte pas plus de 1000Â mÂ² de zone humide"),
    ("surface_lt_400", "n'impacte pas plus de 400Â mÂ² de zone inondable"),
    (
        "runoff_lt_10000",
        "a une surface totale, augmentĂ©e de l'aire d'Ă©coulement d'eaux de pluie interceptĂ©e, infĂ©rieure Ă  1Â ha",
    ),
)


CRITERION_RESULTS = Choices(
    ("soumis", _("Seuil franchi")),
    ("non_soumis", _("Seuil non franchi")),
    ("action_requise", _("Action requise")),
    ("non_applicable", _("Non concernĂ©")),
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
    result = models.CharField(_("Result"), max_length=32, choices=CRITERION_RESULTS)
    required_action = models.TextField(
        _("Required action"), choices=ACTIONS, blank=True
    )
    probability = models.IntegerField(
        _("Probability"),
        choices=PROBABILITIES,
        null=True,
        blank=True,
    )
    criterion = models.CharField(_("Criterion"), max_length=128, choices=CRITERIONS)
    description_md = models.TextField(_("Description"))
    description_html = models.TextField(_("Description (html)"))
    map = models.ImageField(_("Map"), null=True, blank=True)
    legend_md = models.TextField(_("Legend"), blank=True)
    legend_html = models.TextField(_("Legend (html)"), blank=True)

    class Meta:
        verbose_name = _("Criterion")
        verbose_name_plural = _("Criterions")
        unique_together = [("evaluation", "criterion")]

    def __str__(self):
        return mark_safe(self.get_criterion_display())

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


def additional_data_file_format(instance, filename):
    _, extension = splitext(filename)
    return f"requests/{instance.reference}{extension}"


USER_TYPES = Choices(
    ("instructor", "Un service instruction urbanisme"),
    ("petitioner", "Un porteur de projet ou maĂ®tre d'Å“uvre"),
)


class Request(models.Model):
    """An evaluation request by a petitioner."""

    reference = models.CharField(
        _("Reference"),
        max_length=64,
        null=True,
        default=generate_reference,
        unique=True,
        db_index=True,
    )

    # Project localisation
    address = models.TextField(_("Address"))
    parcels = models.ManyToManyField("geodata.Parcel", verbose_name=_("Parcels"))

    # Project specs
    application_number = models.CharField(
        _("Application number"),
        blank=True,
        max_length=15,
        validators=[application_number_validator],
    )
    created_surface = models.IntegerField(
        _("Created surface"),
        null=True,
        blank=True,
        help_text=_("In square meters"),
    )
    existing_surface = models.IntegerField(
        _("Existing surface"), null=True, blank=True, help_text=_("In square meters")
    )
    project_description = models.TextField(
        _("Project description, comments"), blank=True
    )
    additional_data = models.FileField(
        _("Additional data"),
        upload_to=additional_data_file_format,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "zip"])],
    )

    # Petitioner data
    user_type = models.CharField(
        choices=USER_TYPES,
        default=USER_TYPES.instructor,
        max_length=32,
        verbose_name=_("Who are you?"),
    )
    contact_email = models.EmailField(_("E-mail"), blank=True)
    project_sponsor_emails = ArrayField(
        models.EmailField(),
        verbose_name=_("Project sponsor email(s)"),
        blank=True,
        default=list,
    )
    project_sponsor_phone_number = PhoneNumberField(
        _("Project sponsor phone number"), max_length=20, blank=True
    )
    other_contacts = models.TextField(_("Other contacts"), blank=True)
    send_eval_to_sponsor = models.BooleanField(
        _("Send evaluation to project sponsor"), default=True
    )

    # Meta fields
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Evaluation request")
        verbose_name_plural = _("Evaluation requests")

    def __str__(self):
        if self.application_number:
            ref = f"{self.reference} ({self.application_number})"
        else:
            ref = self.reference

        return ref

    def get_parcel_map_url(self):
        """Return an url to a parcel visualization map."""

        parcel_refs = [parcel.reference for parcel in self.parcels.all()]
        qd = QueryDict(mutable=True)
        qd.setlist("parcel", parcel_refs)
        map_url = reverse("map")

        url = f"{map_url}?{qd.urlencode()}"
        return url

    def get_parcel_geojson_export_url(self):
        """Return an url to download the parcels in geojson."""

        parcel_refs = [parcel.reference for parcel in self.parcels.all()]
        qd = QueryDict(mutable=True)
        qd.setlist("parcel", parcel_refs)
        map_url = reverse("parcels_export")

        url = f"{map_url}?{qd.urlencode()}"
        return url


def request_file_format(instance, filename):
    _, extension = splitext(filename)
    return f"requests/{instance.request_id}{extension}"


class RequestFile(models.Model):
    """Store additional files for a single request."""

    request = models.ForeignKey(
        "Request", on_delete=models.PROTECT, related_name="additional_files"
    )
    file = models.FileField(
        _("File"),
        upload_to=request_file_format,
        storage=get_storage_class(settings.UPLOAD_FILE_STORAGE),
    )
    name = models.CharField(_("Name"), blank=True, max_length=1024)

    class Meta:
        verbose_name = _("Request file")
        verbose_name_plural = _("Request files")
