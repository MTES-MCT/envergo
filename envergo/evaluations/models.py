import logging
import secrets
import uuid
from enum import Enum
from os.path import splitext
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.postgres.fields import ArrayField
from django.core.files.storage import storages
from django.core.mail import EmailMultiAlternatives
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import QuerySet
from django.db.models.signals import post_save
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from model_utils.choices import Choices
from phonenumber_field.modelfields import PhoneNumberField

from envergo.evaluations.validators import application_number_validator
from envergo.geodata.models import Department
from envergo.moulinette.utils import MoulinetteUrl
from envergo.utils.markdown import markdown_to_html
from envergo.utils.tools import get_base_url
from envergo.utils.urls import remove_mtm_params, update_qs

logger = logging.getLogger(__name__)

# WGS84, geodetic coordinates, units in degrees
# Good for storing data and working wordwide
EPSG_WGS84 = 4326

# Projected coordinates
# Used for displaying tiles in web map systems (OSM, GoogleMaps)
# Good for working in meters
EPSG_MERCATOR = 3857


# XXX rename petitioner to project owner
USER_TYPES = Choices(
    ("instructor", "Un service instruction urbanisme"),
    ("petitioner", "Un porteur de projet ou maître d'œuvre"),
)


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

# All possible result codes for evaluation criteria
RESULTS = Choices(
    ("soumis", "Soumis"),
    ("non_soumis", "Non soumis"),
    ("action_requise", "Action requise"),
    ("non_disponible", "Non disponible"),
    ("cas_par_cas", "Cas par cas"),
    ("systematique", "Soumis"),
    ("non_applicable", "Non applicable"),
    ("non_concerne", "Non concerné"),
    ("a_verifier", "À vérifier"),
    ("iota_a_verifier", "En cas de dossier Loi sur l'eau"),
    ("interdit", "Interdit"),
    (
        "non_active",
        "Non disponible",
    ),  # Same message for users, but we need to separate `non_active` and `non_disponible`
    ("derogation_inventaire", "Dérogation"),
    ("derogation_simplifiee", "Dérogation allégée"),
    ("dispense", "Dispense"),
    ("dispense_sous_condition", "Dispense sous condition"),
    ("soumis_ou_pac", "Soumis"),
    ("soumis_declaration", "Déclaration"),
    ("soumis_autorisation", "Autorisation"),
)

RESULT_CASCADE = [
    RESULTS.interdit,
    RESULTS.systematique,
    RESULTS.cas_par_cas,
    RESULTS.soumis_ou_pac,
    RESULTS.soumis_declaration,
    RESULTS.soumis,
    RESULTS.soumis_autorisation,
    RESULTS.derogation_inventaire,
    RESULTS.derogation_simplifiee,
    RESULTS.dispense_sous_condition,
    RESULTS.action_requise,
    RESULTS.a_verifier,
    RESULTS.iota_a_verifier,
    RESULTS.non_soumis,
    RESULTS.dispense,
    RESULTS.non_concerne,
    RESULTS.non_disponible,
    RESULTS.non_applicable,
    RESULTS.non_active,
]

_missing_results = [key for (key, label) in RESULTS if key not in RESULT_CASCADE]
if _missing_results:
    raise ValueError(
        f"The following RESULTS are missing in RESULT_CASCADE: {_missing_results}"
    )


# All possible result codes for a single evaluation
# This is for legacy evaluations only
EVAL_RESULTS = Choices(
    ("soumis", "Soumis"),
    ("non_soumis", "Non soumis"),
    ("action_requise", "Action requise"),
)


class TagStyleEnum(Enum):
    Green = 1
    Grey = 2
    Yellow = 3
    LightRed = 4
    Orange = 5
    StrongRed = 6


TAG_STYLES_BY_RESULT = {
    RESULTS.soumis: TagStyleEnum.LightRed,
    RESULTS.soumis_ou_pac: TagStyleEnum.LightRed,
    RESULTS.action_requise: TagStyleEnum.Yellow,
    RESULTS.non_soumis: TagStyleEnum.Green,
    RESULTS.non_disponible: TagStyleEnum.Grey,
    RESULTS.non_applicable: TagStyleEnum.Grey,
    RESULTS.cas_par_cas: TagStyleEnum.Orange,
    RESULTS.systematique: TagStyleEnum.LightRed,
    RESULTS.non_concerne: TagStyleEnum.Green,
    RESULTS.a_verifier: TagStyleEnum.Yellow,
    RESULTS.iota_a_verifier: TagStyleEnum.Yellow,
    RESULTS.interdit: TagStyleEnum.StrongRed,
    RESULTS.non_active: TagStyleEnum.Grey,
    RESULTS.derogation_inventaire: TagStyleEnum.LightRed,
    RESULTS.derogation_simplifiee: TagStyleEnum.LightRed,
    RESULTS.dispense: TagStyleEnum.Green,
    RESULTS.dispense_sous_condition: TagStyleEnum.Orange,
    RESULTS.soumis_declaration: TagStyleEnum.LightRed,
    RESULTS.soumis_autorisation: TagStyleEnum.LightRed,
    "declaration": TagStyleEnum.Green,
    "autorisation": TagStyleEnum.LightRed,
    "hors_regime_unique": TagStyleEnum.Grey,
}
_missing_results = [key for (key, label) in RESULTS if key not in TAG_STYLES_BY_RESULT]
if _missing_results:
    raise ValueError(
        f"The following RESULTS are missing in TAG_STYLES_BY_RESULT: {_missing_results}"
    )


class EvaluationQuerySet(QuerySet):
    def update(self, **kwargs):
        res = super().update(**kwargs)
        for instance in self:
            # Signal that the save is complete
            post_save.send(
                sender=Evaluation,
                instance=instance,
                created=False,
                update_fields=None,
                raw=False,
                using=self.db,
            )
        return res


class Evaluation(models.Model):
    """A single evaluation for a building permit application.

    Note: the domaine technical name evolved from "évaluation" to "avis réglementaire",
    often shortened in "avis".

    """

    objects = EvaluationQuerySet.as_manager()

    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(
        _("Reference"),
        max_length=64,
        default=generate_reference,
        unique=True,
        db_index=True,
    )

    request = models.OneToOneField(
        "evaluations.Request",
        verbose_name="Demande associée",
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
    project_description = models.TextField(
        _("Project description, comments"), blank=True
    )

    address = models.TextField(_("Address"))
    details_md = models.TextField(
        _("Notice additional mention"),
        blank=True,
        help_text=_(
            """Will be included in the notice page.
            Only simple markdown (*bold*, _italic_, [links](https://url), newlines)."""
        ),
    )
    details_html = models.TextField(_("Details"), blank=True)
    rr_mention_md = models.TextField(
        _("Email additional mention"),
        blank=True,
        help_text=_(
            """Will be included in the RR email.
            Only simple markdown (*bold*, _italic_, [links](https://url), newlines)."""
        ),
    )
    rr_mention_html = models.TextField(_("Regulatory reminder mention"), blank=True)

    moulinette_url = models.URLField(_("Moulinette url"), max_length=1024)
    moulinette_data = models.JSONField(_("Moulinette metadata"), null=True)

    # Project owner data
    user_type = models.CharField(
        choices=USER_TYPES,
        default=USER_TYPES.instructor,
        max_length=32,
        verbose_name=_("Who are you?"),
    )
    urbanism_department_emails = ArrayField(
        models.EmailField(),
        blank=True,
        default=list,
        verbose_name="Email service ADS",
    )
    urbanism_department_phone = PhoneNumberField(
        _("Urbanism department phone number"), max_length=20, blank=True
    )

    project_owner_emails = ArrayField(
        models.EmailField(),
        verbose_name=_("Project owner email(s)"),
        blank=True,
        default=list,
    )
    project_owner_phone = PhoneNumberField(
        _("Project owner phone"), max_length=20, blank=True
    )
    project_owner_company = models.CharField(
        _("Project owner company"), max_length=128, blank=True
    )
    other_contacts = models.TextField(_("Other contacts"), blank=True)
    send_eval_to_project_owner = models.BooleanField(
        _("Send evaluation to project sponsor"), default=True
    )
    is_icpe = models.BooleanField(_("Is ICPE?"), default=False)
    display_actions_to_take = models.BooleanField(
        "Afficher les actions à mener ?", default=False
    )
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)
    updated_at = models.DateTimeField(_("Date updated"), auto_now=True)

    class Meta:
        verbose_name = "Avis"
        verbose_name_plural = "Avis"

    def __str__(self):
        return self.reference

    def get_absolute_url(self):
        return reverse("evaluation_detail", args=[self.reference])

    def save(self, *args, **kwargs):
        self.details_html = markdown_to_html(self.details_md)
        self.rr_mention_html = markdown_to_html(self.rr_mention_md)
        self.moulinette_data = MoulinetteUrl(self.moulinette_url).params
        super().save(*args, **kwargs)

    @property
    def application_number_display(self):
        an = self.application_number
        # Those are non-breaking spaces
        return f"{an[0:2]} {an[2:5]} {an[5:8]} {an[8:10]} {an[10:]}"

    @cached_property
    def moulinette_params(self):
        """Return the evaluation params as provided in the moulinette url."""
        return MoulinetteUrl(self.moulinette_url).params

    def get_moulinette(self):
        """Return the moulinette instance for this evaluation."""
        from envergo.moulinette.models import MoulinetteAmenagement

        if not hasattr(self, "_moulinette"):
            data = self.moulinette_params
            moulinette_data = {"initial": data, "data": data}
            self._moulinette = (
                MoulinetteAmenagement(  # there is only Amenagement evaluations
                    moulinette_data
                )
            )

        return self._moulinette

    def can_send_regulatory_reminder(self):
        """Return True if a regulatory reminder can be sent for this evaluation."""

        return self.request and self.moulinette_url

    def get_evaluation_email(self):
        return EvaluationEmail(self)

    def is_eligible_to_self_declaration(self):
        """Should we display the "self declare" call to action?"""
        if self.is_icpe:
            return False

        moulinette = self.get_moulinette()
        all_criteria = []
        for regulation in moulinette.regulations:
            all_criteria.extend(regulation.criteria.all())

        return any(
            criterion._evaluator.eligible_to_self_declaration
            for criterion in all_criteria
        )

    def unpublish(self):
        """Unpublish the evaluation."""

        self.versions.update(published=False)

    def create_version(self, author, message):
        content = self.render_content()
        version = EvaluationVersion(
            evaluation=self, created_by=author, content=content, message=message
        )
        return version

    def render_content(self):
        """Render the evaluation as a static HTML document.

        The html is just the main html content, i.e the content that should
        be inserted in the main `article` html tag in the base.html template.
        """
        moulinette = self.get_moulinette()
        template = "evaluations/_content.html"

        # Evaluations exist only for Envergo Amenagement:
        evaluation_url = f"{get_base_url(settings.ENVERGO_AMENAGEMENT_DOMAIN)}{self.get_absolute_url()}"
        share_print_url = update_qs(
            remove_mtm_params(evaluation_url), {"mtm_campaign": "print-ar"}
        )

        emulated_request = HttpRequest()
        emulated_request.GET = MoulinetteUrl(self.moulinette_url).querydict

        context = {
            "evaluation": self,
            "moulinette": moulinette,
            "evaluation_url": evaluation_url,
            "share_print_url": share_print_url,
            **moulinette.get_extra_context(emulated_request),
        }
        context.update(moulinette.catalog)
        content = render_to_string(template, context)
        return content


class EvaluationVersion(models.Model):
    """An evaluation version with a fixed content.

    By design, an evaluation is dynamic, the content is generated and displayed
    everytime it is rendered.

    However, we need evaluation results and content to be fixed in time, because they
    will now be considered legal documents.
    """

    evaluation = models.ForeignKey(
        "Evaluation",
        on_delete=models.CASCADE,
        verbose_name=_("Evaluation"),
        related_name="versions",
    )
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        verbose_name=_("Created by"),
        related_name="evaluation_versions",
    )
    content = models.TextField(_("Content"))
    published = models.BooleanField(_("Is published?"), default=True)
    message = models.CharField(
        _("Message"),
        max_length=1024,
        help_text=_("This message will be displayed to users."),
    )

    class Meta:
        verbose_name = _("Evaluation version")
        verbose_name_plural = _("Evaluation versions")
        ordering = ("-created_at",)

        # Let's make sure a single version can be published at a time
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation"],
                condition=models.Q(published=True),
                name="unique_published_version",
            )
        ]


class EvaluationEmail:
    """A custom object dedicated to handling "avis réglementaires" emails for evaluations."""

    def __init__(self, evaluation):
        self.evaluation = evaluation
        self.moulinette = evaluation.get_moulinette()

    def get_email(self, request):
        evaluation = self.evaluation
        moulinette = evaluation.get_moulinette()
        result = moulinette.result
        txt_mail_template = f"evaluations/admin/eval_email_{result}.txt"
        html_mail_template = f"evaluations/admin/eval_email_{result}.html"

        # Should we display the "à transmettre au porteur" mention?
        to_be_transmitted = all(
            (
                not evaluation.is_icpe,
                evaluation.user_type == USER_TYPES.instructor,
                result != "non_soumis",
                not evaluation.send_eval_to_project_owner,
            )
        )
        # Should we display the links to self-transfer to the project owner?
        display_transfer_links = all(
            (
                to_be_transmitted,
                evaluation.project_owner_emails,
            )
        )
        # Those as parameters to pass on to the Tally form
        transfer_form_params = {
            "societe": evaluation.project_owner_company,
            "telephone": evaluation.project_owner_phone,
            "email": ", ".join(evaluation.project_owner_emails),
            "ref_envergo": evaluation.reference,
            "adresse": evaluation.address,
            "num_demande_permis": evaluation.application_number,
        }
        # Should we display the custom warning for icpe projects?
        icpe_not_transmitted = all(
            (
                evaluation.is_icpe,
                evaluation.send_eval_to_project_owner,
                evaluation.user_type == USER_TYPES.instructor,
            )
        )
        context = {
            "evaluation": evaluation,
            "is_icpe": evaluation.is_icpe,
            "rr_mention_md": evaluation.rr_mention_md,
            "rr_mention_html": evaluation.rr_mention_html,
            "moulinette": moulinette,
            "evaluation_link": request.build_absolute_uri(
                evaluation.get_absolute_url()
            ),
            "self_declaration_link": request.build_absolute_uri(
                reverse("self_declaration", args=[evaluation.reference])
            ),
            "to_be_transmitted": to_be_transmitted,
            "display_transfer_links": display_transfer_links,
            "transfer_eval_email_form_id": settings.TRANSFER_EVAL_EMAIL_FORM_ID,
            "transfer_form_params": urlencode(transfer_form_params),
            "icpe_not_transmitted": icpe_not_transmitted,
            "required_actions_soumis": list(moulinette.all_required_actions_soumis()),
            "required_actions_interdit": list(
                moulinette.all_required_actions_interdit()
            ),
        }
        txt_body = render_to_string(txt_mail_template, context)
        html_body = render_to_string(html_mail_template, context)

        recipients = self.get_recipients()
        cc_recipients = self.get_cc_recipients()
        bcc_recipients = self.get_bcc_recipients()

        subject = "Avis réglementaire"
        if evaluation.address:
            subject += f" / {evaluation.address}"

        email = EmailMultiAlternatives(
            from_email=settings.FROM_EMAIL["amenagement"]["evaluations"],
            subject=subject,
            body=txt_body,
            to=recipients,
            cc=cc_recipients,
            bcc=bcc_recipients,
        )
        email.attach_alternative(html_body, "text/html")
        return email

    def get_recipients(self):
        evaluation = self.evaluation
        result = self.moulinette.result

        if evaluation.user_type == USER_TYPES.instructor:
            if evaluation.send_eval_to_project_owner and not evaluation.is_icpe:
                if result in ("interdit", "soumis", "action_requise"):
                    recipients = evaluation.project_owner_emails
                else:
                    recipients = evaluation.urbanism_department_emails

            else:
                recipients = evaluation.urbanism_department_emails
        else:
            recipients = evaluation.project_owner_emails

        # We have to sort results to make the tests pass
        return sorted(list(set(recipients)))

    def get_cc_recipients(self):
        evaluation = self.evaluation
        result = self.moulinette.result

        cc_recipients = []

        if all(
            (
                not evaluation.is_icpe,
                evaluation.user_type == USER_TYPES.instructor,
                evaluation.send_eval_to_project_owner,
                result in ("interdit", "soumis", "action_requise"),
            )
        ):
            cc_recipients = evaluation.urbanism_department_emails

        return sorted(list(set(cc_recipients)))

    def get_bcc_recipients(self):
        evaluation = self.evaluation
        moulinette = self.moulinette
        config = moulinette.get_config()

        bcc_recipients = []

        if all(
            (
                not evaluation.is_icpe,
                evaluation.user_type == USER_TYPES.instructor,
                evaluation.send_eval_to_project_owner,
            )
        ):
            if moulinette.loi_sur_leau and moulinette.loi_sur_leau.result in [
                "soumis",
                "soumis_ou_pac",
            ]:
                if config.ddtm_water_police_email:
                    bcc_recipients.append(config.ddtm_water_police_email)
                else:
                    logger.warning("Manque l'email de la police de l'eau")

            if (
                moulinette.natura2000
                and moulinette.natura2000.result == "soumis"
                and not moulinette.natura2000.ein_out_of_n2000_site()
            ):
                if config.ddtm_n2000_email:
                    bcc_recipients.append(config.ddtm_n2000_email)
                else:
                    logger.warning("Manque l'email de la DDT(M) N2000")

            if moulinette.eval_env and moulinette.eval_env.result in (
                "systematique",
                "cas_par_cas",
            ):
                if config.dreal_eval_env_email:
                    bcc_recipients.append(config.dreal_eval_env_email)
                else:
                    logger.warning("Manque l'email de la DREAL pôle Éval Env")

        if (
            evaluation.user_type == USER_TYPES.instructor
            and evaluation.send_eval_to_project_owner
            and self.moulinette.sage
            and self.moulinette.sage.result
            in (
                "interdit",
                "soumis",
                "action_requise",
            )
        ):
            for perimeter, result in self.moulinette.sage.results_by_perimeter.items():
                if result not in ("interdit", "soumis", "action_requise"):
                    continue
                if perimeter.contact_email:
                    bcc_recipients.append(perimeter.contact_email)
                else:
                    logger.warning(
                        f"Manque l'email du périmètre de SAGE : {perimeter.name}"
                    )

        return sorted(list(set(bcc_recipients)))


def additional_data_file_format(instance, filename):
    _, extension = splitext(filename)
    return f"requests/{instance.reference}{extension}"


class Request(models.Model):
    """An evaluation request by a project owner."""

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
    moulinette_url = models.URLField(_("Moulinette url"), max_length=1024, blank=True)

    # Project specs
    application_number = models.CharField(
        _("Application number"),
        blank=True,
        max_length=15,
        validators=[application_number_validator],
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
    urbanism_department_emails = ArrayField(
        models.EmailField(),
        blank=True,
        default=list,
        verbose_name=_("Urbanism department email address(es)"),
    )
    urbanism_department_phone = PhoneNumberField(
        _("Urbanism department phone number"), max_length=20, blank=True
    )

    project_owner_emails = ArrayField(
        models.EmailField(),
        verbose_name=_("Project sponsor email(s)"),
        blank=True,
        default=list,
    )
    project_owner_phone = PhoneNumberField(
        _("Project sponsor phone number"), max_length=20, blank=True
    )
    other_contacts = models.TextField(_("Other contacts"), blank=True)
    send_eval_to_project_owner = models.BooleanField(
        _("Send evaluation to project sponsor"), default=True
    )
    obfuscation_key = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name="Clé d'obfuscation",
    )

    # Meta fields
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    # We have to save the Request before the end of the form wizard, because we need
    # to attach uploaded files to an existing object.
    # But we need to wait for the latest step to be completed before
    # actually sending the confirmation mails and acks
    submitted = models.BooleanField(_("Submitted"), default=False)

    class Meta:
        verbose_name = _("Evaluation request")
        verbose_name_plural = _("Evaluation requests")

    def __str__(self):
        if self.application_number:
            ref = f"{self.reference} ({self.application_number})"
        else:
            ref = self.reference

        return ref

    @cached_property
    def moulinette_params(self):
        """Return the evaluation params as provided in the moulinette url."""
        return MoulinetteUrl(self.moulinette_url).params

    def is_from_instructor(self):
        """Shortcut property"""
        return self.user_type == USER_TYPES.instructor

    def get_requester_emails(self):
        """Return emails of the user who requested the evaluation."""

        return (
            self.urbanism_department_emails
            if self.is_from_instructor()
            else self.project_owner_emails
        )

    def create_evaluation(self):
        """Create an evaluation from this evaluation request."""

        # Let's make sure there is not already an
        # evaluation associated with this request
        try:
            self.evaluation
        except Evaluation.DoesNotExist:
            # We're good
            pass
        else:
            error = _("There already is an evaluation associated with this request.")
            raise ValueError(error)

        evaluation = Evaluation.objects.create(
            reference=self.reference,
            urbanism_department_emails=self.urbanism_department_emails,
            urbanism_department_phone=self.urbanism_department_phone,
            request=self,
            application_number=self.application_number,
            address=self.address,
            project_description=self.project_description,
            user_type=self.user_type,
            project_owner_emails=self.project_owner_emails,
            project_owner_phone=self.project_owner_phone,
            other_contacts=self.other_contacts,
            send_eval_to_project_owner=self.send_eval_to_project_owner,
        )
        return evaluation

    @property
    def upload_files_url(self):
        """return the obfuscated url to the upload files UI"""
        url = reverse("request_eval_wizard_step_3", args=[self.reference])
        return f"{url}?{urlencode({'clef': self.obfuscation_key})}"

    @property
    def upload_files_api_url(self):
        """return the obfuscated url to the upload files API"""
        url = reverse("request_eval_wizard_step_3_upload", args=[self.reference])
        return f"{url}?{urlencode({'clef': self.obfuscation_key})}"


def request_file_format(instance, filename):
    _, extension = splitext(filename)
    return f"requests/{instance.request.reference}/{uuid.uuid4()}{extension}"


def get_upload_storage():
    """Return the correct storage.

    We cannot use a simple lambda because django migrations cannot serialize them.
    """
    return storages["upload"]


class RequestFile(models.Model):
    """Store additional files for a single request."""

    request = models.ForeignKey(
        "Request", on_delete=models.PROTECT, related_name="additional_files"
    )
    file = models.FileField(
        _("File"),
        upload_to=request_file_format,
        storage=get_upload_storage,
    )
    name = models.CharField(_("Name"), blank=True, max_length=1024)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("Request file")
        verbose_name_plural = _("Request files")


class RegulatoryNoticeLog(models.Model):
    """Store regulatory notice email logs."""

    evaluation = models.ForeignKey(
        "Evaluation",
        verbose_name="Avis",
        on_delete=models.CASCADE,
        related_name="regulatory_notice_logs",
    )
    sender = models.ForeignKey(
        "users.User", verbose_name=_("Sender"), on_delete=models.PROTECT
    )
    frm = models.EmailField(_("From"))
    to = ArrayField(models.EmailField(), verbose_name=_("To"))
    cc = ArrayField(models.EmailField(), verbose_name=_("Cc"))
    bcc = ArrayField(models.EmailField(), verbose_name=_("Bcc"))
    txt_body = models.TextField(_("Text body"))
    html_body = models.TextField(_("Html body"))
    subject = models.CharField(_("Subject"), max_length=1024)
    sent_at = models.DateTimeField(_("Date sent"), default=timezone.now)
    moulinette_data = models.JSONField(_("Moulinette data"), null=True, blank=True)
    moulinette_result = models.JSONField(_("Moulinette result"), null=True, blank=True)
    message_id = models.CharField(_("Message id"), max_length=1024, blank=True)

    class Meta:
        verbose_name = _("Regulatory notice log")
        verbose_name_plural = _("Regulatory notice logs")
        ordering = ("-sent_at",)


class RecipientStatus(models.Model):
    regulatory_notice_log = models.ForeignKey(
        RegulatoryNoticeLog, on_delete=models.CASCADE, related_name="recipient_statuses"
    )
    recipient = models.EmailField(_("Recipient"))
    status = models.CharField(_("Status"), max_length=64)
    latest_status = models.DateTimeField(_("Latest status"))
    nb_opened = models.IntegerField(_("Nb opened"), default=0)
    latest_opened = models.DateTimeField(_("Latest opened"), null=True)
    nb_clicked = models.IntegerField(_("Nb clicked"), default=0)
    latest_clicked = models.DateTimeField(_("Latest clicked"), null=True)
    on_error = models.BooleanField(_("On error"), default=False)
    reject_reason = models.CharField(_("Reject reason"), max_length=64, blank=True)

    class Meta:
        verbose_name = _("Recipient status")
        verbose_name_plural = _("Recipient statuses")
        constraints = [
            models.UniqueConstraint(
                name="unique_index", fields=["regulatory_notice_log", "recipient"]
            )
        ]
