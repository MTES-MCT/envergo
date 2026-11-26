import inspect
import logging
import secrets
from datetime import date, datetime, timedelta
from os.path import splitext
from urllib.parse import urlparse

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import Q
from django.http import QueryDict
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from model_utils import Choices, FieldTracker

from envergo.evaluations.models import generate_reference
from envergo.geodata.models import Department
from envergo.hedges.models import HedgeCategory, HedgeData
from envergo.moulinette.forms import TriageFormHaie
from envergo.moulinette.models import MoulinetteHaie, MoulinetteHaieUrlMixin, Regulation
from envergo.moulinette.utils import MoulinetteUrl
from envergo.petitions.demarche_numerique.models import Dossier
from envergo.petitions.services import (
    DEMARCHE_NUMERIQUE_STATUS_MAPPING,
    attestation_non_opposition_pdf,
    declaration_receipt_message,
    dossier_state_changed_outside_guh_alert,
    dossier_submission_alert,
    log_dossier_submission_event,
    update_demarche_numerique_status,
)
from envergo.utils.models import ResultSnapshotBase
from envergo.utils.urls import extract_param_from_url, update_qs

logger = logging.getLogger(__name__)


class DossierNotSynchronized(Exception):
    """The « Démarche numérique » dossier must be synchronized before being read."""


DOSSIER_STATES = Choices(
    ("draft", _("Draft")),
    ("prefilled", _("Prefilled")),
    ("accepte", _("Accepted")),
    ("en_construction", _("Under construction")),
    ("en_instruction", _("Under instruction")),
    ("refuse", _("Refused")),
    ("sans_suite", _("No follow-up")),
)

UNSUBMITTED_DOSSIER_STATES = (DOSSIER_STATES.draft, DOSSIER_STATES.prefilled)

STAGES = Choices(
    ("to_be_processed", "À instruire"),
    ("instruction_d", "Instruction déclaration"),
    ("instruction_a", "Instruction autorisation"),
    ("instruction_h", "Instruction hors régime unique"),
    ("preparing_decision", "Rédaction décision"),
    ("notification", "Notification / Publicité"),
    ("closed", "Dossier clos"),
)

INSTRUCTION_STAGES = (
    STAGES.instruction_d,
    STAGES.instruction_a,
    STAGES.instruction_h,
)

# Stages where the decision on a deposited dossier is still pending.
PENDING_DECISION_STAGES = INSTRUCTION_STAGES + (
    STAGES.preparing_decision,
    STAGES.notification,
)

DECISIONS = Choices(
    ("unset", "À déterminer"),
    ("tacit_agreement", "Accord tacite"),
    ("express_agreement", "Accord exprès"),
    ("opposition", "Opposition"),
    ("dropped", "Classé sans suite"),
)


class SilenceRule(models.TextChoices):
    """What the administration's silence means once the instruction deadline passes."""

    AGREEMENT = "agreement", "Silence vaut accord"
    REFUSAL = "refusal", "Silence vaut refus"


# Instruction stages of the régime unique. Other stages carry no silence rule.
SILENCE_RULE_BY_INSTRUCTION_STAGE = {
    STAGES.instruction_d: SilenceRule.AGREEMENT,
    STAGES.instruction_a: SilenceRule.REFUSAL,
}

FORBIDDEN_STAGE_TRANSITIONS = {
    (
        "to_be_processed",
        "closed",
    ): "Pour clore le dossier, il faut passer par une étape intermédiaire (autre que « À instruire »).",
    (
        "closed",
        "closed",
    ): "Pour pouvoir changer la décision d'un dossier clos il faut d'abord le repasser à une étape d'instruction.",
}

LOG_TYPES = Choices(
    ("status_change", "Changement d'état"),
    ("suspension", "Demande de compléments"),
    ("resumption", "Compléments reçus"),
)


def dn_archive_file_format(instance, filename):
    _, extension = splitext(filename)
    secret = secrets.token_urlsafe(16)
    return f"dn_archives/{instance.reference}_{secret}{extension}"


def prefectural_order_file_format(instance, filename):
    """Build the upload path for a prefectural order file.

    The random secret makes the public url impossible to guess, since the
    file is stored on a public-read bucket. `instance` is a StatusLog.
    """
    _, extension = splitext(filename)
    secret = secrets.token_urlsafe(16)
    reference = instance.petition_project.reference
    return f"arrete_prefectoral/{reference}_{secret}{extension}"


def read_submission_date(fetched_dossier: dict) -> date:
    """The dossier's dépôt date, or today when « Démarche numérique » gives none."""
    raw_date_depot = fetched_dossier.get("dateDepot")
    if raw_date_depot:
        submission_date = parser.isoparse(raw_date_depot).date()
    else:
        submission_date = timezone.localdate()
    return submission_date


def read_last_modification(dossier: dict | None) -> datetime | None:
    """When « Démarche numérique » last modified the dossier, or None when unknown."""
    raw_last_modification = (dossier or {}).get("dateDerniereModification")
    if raw_last_modification:
        last_modification = parser.isoparse(raw_last_modification)
    else:
        last_modification = None
    return last_modification


def declaration_due_date(submission_date: date) -> date:
    """End of the two-month tacit agreement delay of a déclaration."""
    return submission_date + relativedelta(months=2)


class PetitionProjectQuerySet(models.QuerySet):
    """Named selections of petition projects."""

    def regime_unique(self):
        """The dossiers under the régime unique."""
        return self.filter(_category=HedgeCategory.ru)

    def decision_pending(self):
        """The dossiers still waiting for a decision."""
        return self.filter(stage__in=PENDING_DECISION_STAGES)

    def not_suspended(self):
        """The dossiers not waiting for additional documents from the applicant."""
        return self.filter(is_additional_information_requested=False)

    def due_for_tacit_agreement(self, today: date):
        """The dossiers whose silence became agreement on or before `today`."""
        return (
            self.regime_unique()
            .decision_pending()
            .not_suspended()
            .filter(silence_rule=SilenceRule.AGREEMENT, silence_deadline__lte=today)
            .select_related("department", "hedge_data")
            .defer("department__geometry")
        )


class InstructionMixin:
    """The instruction events of a dossier.

    Each action builds its status log before changing the dossier. The log reads
    the dossier's previous state.
    """

    def start_instruction(self, *, submission_date):
        """On dépôt, move the dossier into its instruction stage."""
        instruction_stage = self._first_instruction_stage()
        agreement_deadline = self._agreement_deadline_on_entering(
            instruction_stage, submission_date
        )

        log = StatusLog(
            petition_project=self,
            type=LOG_TYPES.status_change,
            stage=instruction_stage,
            decision=DECISIONS.unset,
            # The instruction is due when silence turns into an agreement.
            due_date=agreement_deadline,
            agreement_deadline=agreement_deadline,
            update_comment="Dépôt du dossier : passage automatique en instruction.",
        )
        self.stage = instruction_stage
        self.decision = DECISIONS.unset
        self.due_date = agreement_deadline
        self.silence_rule = self.silence_rule_in(instruction_stage)
        self.silence_deadline = agreement_deadline
        return self._record_event(log)

    def request_complements(self, *, complements_due_date, applicant_message, author):
        """An instructor suspends the instruction until the applicant sends compléments."""
        log = StatusLog(
            petition_project=self,
            type=LOG_TYPES.suspension,
            stage=self.stage,
            decision=self.decision,
            due_date=complements_due_date,
            original_due_date=self.due_date,
            applicant_message=applicant_message,
            update_comment="Suspension de l’instruction, message envoyé au demandeur.",
            created_by=author,
        )
        self.is_additional_information_requested = True
        self.due_date = complements_due_date
        return self._record_event(log)

    def receive_complements(self, *, received_on, due_date, author):
        """An instructor resumes the instruction on receiving the compléments.

        When silence means agreement, the delay restarts on `received_on`, and its
        end becomes the due date in place of `due_date`. The applicant gets a new
        récépissé stating it.
        """
        restarts_agreement_delay = self.silence_rule == SilenceRule.AGREEMENT
        if restarts_agreement_delay:
            agreement_deadline = declaration_due_date(received_on)
            due_date = agreement_deadline
            applicant_message = declaration_receipt_message(self, received_on, due_date)
        else:
            agreement_deadline = None
            applicant_message = ""

        if due_date:
            update_comment = "Reprise de l’instruction, date d'échéance ajustée."
        else:
            update_comment = "Reprise de l’instruction."

        log = StatusLog(
            petition_project=self,
            type=LOG_TYPES.resumption,
            stage=self.stage,
            decision=self.decision,
            info_receipt_date=received_on,
            due_date=due_date,
            agreement_deadline=agreement_deadline,
            applicant_message=applicant_message,
            update_comment=update_comment,
            created_by=author,
        )
        self.is_additional_information_requested = False
        self.due_date = due_date
        if restarts_agreement_delay:
            self.silence_deadline = agreement_deadline
        return self._record_event(log)

    def switch_to_authorization(
        self,
        *,
        status_date,
        refusal_deadline,
        applicant_message,
        update_comment,
        author,
    ):
        """An instructor moves a déclaration into authorisation.

        Silence then means refusal at `refusal_deadline`.
        """
        notice = "Message envoyé au demandeur."
        if update_comment:
            log_comment = f"{update_comment}\n{notice}"
        else:
            log_comment = notice

        log = StatusLog(
            petition_project=self,
            type=LOG_TYPES.status_change,
            stage=STAGES.instruction_a,
            decision=self.decision,
            status_date=status_date,
            due_date=refusal_deadline,
            refusal_deadline=refusal_deadline,
            applicant_message=applicant_message,
            update_comment=log_comment,
            created_by=author,
        )
        self.stage = STAGES.instruction_a
        self.due_date = refusal_deadline
        self.silence_rule = SilenceRule.REFUSAL
        self.silence_deadline = refusal_deadline
        return self._record_event(log)

    def close_by_express_decision(
        self,
        *,
        status_date,
        decision,
        prefectural_order,
        applicant_message,
        update_comment,
        author,
    ):
        """An instructor closes the dossier with an express decision.

        `prefectural_order` is the decision document, or None when the decision has none.
        """
        log = StatusLog(
            petition_project=self,
            type=LOG_TYPES.status_change,
            stage=STAGES.closed,
            status_date=status_date,
            decision=decision,
            due_date=None,
            prefectural_order=prefectural_order,
            applicant_message=applicant_message,
            update_comment=update_comment,
            created_by=author,
        )
        self.stage = STAGES.closed
        self.decision = decision
        self.due_date = None
        self.silence_rule = None
        self.silence_deadline = None
        return self._record_event(log)

    def close_by_tacit_agreement(self):
        """The nightly job closes the dossier by tacit agreement, with the attestation de non-opposition."""
        agreement_date = self.silence_deadline
        attestation = ContentFile(
            attestation_non_opposition_pdf(self, agreement_date),
            name="attestation_non_opposition.pdf",
        )
        applicant_message = render_to_string(
            "haie/petitions/tacit_agreement_message.txt"
        )

        log = StatusLog(
            petition_project=self,
            type=LOG_TYPES.status_change,
            stage=STAGES.closed,
            status_date=agreement_date,
            decision=DECISIONS.tacit_agreement,
            due_date=None,
            prefectural_order=attestation,
            applicant_message=applicant_message,
            update_comment=(
                "Clôture automatique : silence vaut accord. "
                "Message envoyé au demandeur avec l’attestation de non-opposition."
            ),
        )
        self.stage = STAGES.closed
        self.decision = DECISIONS.tacit_agreement
        self.due_date = None
        self.silence_rule = None
        self.silence_deadline = None
        return self._record_event(log)

    # Note: This method only exists because the current UI allows for any transition
    # stage transition, even ones that should not be possible.
    # UI is being redesigned right now, so this method is meant to be removed in the end.
    def change_status_manually(
        self, *, status_date, stage, decision, due_date, update_comment, author
    ):
        """An instructor sets the stage, decision and due date freely, outside the named actions.

        Entering a stage where silence means agreement starts the agreement delay on `status_date`.
        The silence deadline stays only while the silence rule stays.
        """
        started_agreement_deadline = self._agreement_deadline_on_entering(
            stage, status_date
        )

        silence_rule_in_new_stage = self._silence_rule_after_entering(stage)
        if started_agreement_deadline:
            silence_deadline = started_agreement_deadline
        elif silence_rule_in_new_stage == self.silence_rule:
            silence_deadline = self.silence_deadline
        else:
            silence_deadline = None

        log = StatusLog(
            petition_project=self,
            type=LOG_TYPES.status_change,
            status_date=status_date,
            stage=stage,
            decision=decision,
            due_date=due_date,
            agreement_deadline=started_agreement_deadline,
            update_comment=update_comment,
            created_by=author,
        )
        self.stage = stage
        self.decision = decision
        self.due_date = due_date
        self.silence_rule = silence_rule_in_new_stage
        self.silence_deadline = silence_deadline
        return self._record_event(log)

    def _first_instruction_stage(self):
        """The stage a dossier enters when its instruction starts."""
        if self.is_regime_unique():
            stage = STAGES.instruction_d
        else:
            stage = STAGES.instruction_h
        return stage

    def _agreement_deadline_on_entering(self, stage, start_date: date) -> date | None:
        """When silence turns into agreement, for a dossier entering `stage` on `start_date`.

        None when silence in `stage` means no agreement, or when the dossier is already there.
        """
        starts_agreement_delay = (
            self.silence_rule_in(stage) == SilenceRule.AGREEMENT and self.stage != stage
        )

        deadline = None
        if starts_agreement_delay:
            deadline = declaration_due_date(start_date)
        return deadline

    def _silence_rule_after_entering(self, stage) -> SilenceRule | None:
        """What silence will mean once the dossier enters `stage`."""
        if stage in INSTRUCTION_STAGES:
            rule = self.silence_rule_in(stage)
        elif stage in PENDING_DECISION_STAGES:
            # Outside instruction, a pending dossier keeps its current rule.
            rule = self.silence_rule
        else:
            rule = None
        return rule

    def _record_event(self, log):
        """Save the event's log and the dossier, mirror them in « Démarche numérique », and return the log."""
        with transaction.atomic():
            log.save()
            self.save()
            self._sync_demarche_numerique_status(log)
            if log.applicant_message:
                self._schedule_applicant_message(log)
        return log

    def _sync_demarche_numerique_status(self, log):
        """Update the « Démarche numérique » status to match the new log, when it differs."""
        new_status = DEMARCHE_NUMERIQUE_STATUS_MAPPING[(log.stage, log.decision)]
        if self.demarche_numerique_state != new_status:
            update_demarche_numerique_status(self, new_status)

    def _schedule_applicant_message(self, log):
        """Queue the log's applicant message for after commit.

        Sent asynchronously, so a DN messagerie failure never blocks the state
        change. The task retry policy handles transient errors. A queuing
        failure is logged and leaves the state change in place.
        """
        # Imported here: the tasks module imports this one.
        from envergo.petitions.tasks import send_applicant_message_async

        transaction.on_commit(
            lambda: send_applicant_message_async.delay(log.pk), robust=True
        )


class PetitionProject(InstructionMixin, MoulinetteHaieUrlMixin, models.Model):
    """A petition project by a project owner.

    A petition project will store any data needed to follow up a request concerning a hedge.
    Both the project owner and the public administration will be able to follow up the request.
    """

    objects = PetitionProjectQuerySet.as_manager()
    tracker = FieldTracker()

    reference = models.CharField(
        _("Reference"),
        max_length=64,
        null=True,
        default=generate_reference,
        unique=True,
        db_index=True,
    )
    moulinette_url = models.URLField(_("Moulinette url"), max_length=1024, blank=True)

    department = models.ForeignKey(
        "geodata.Department",
        on_delete=models.PROTECT,
        related_name="petitionprojects",
        editable=False,
        blank=True,
        null=True,
        verbose_name="Département",
    )

    hedge_data = models.ForeignKey(
        HedgeData,
        on_delete=models.PROTECT,
    )

    _category = models.CharField(
        "Catégorie du dossier",
        max_length=20,
        choices=HedgeCategory.choices,
        db_index=True,
    )

    original_multi_category_moulinette_url = models.URLField(
        "Url de la moulinette multi catégorie d'où a été extrait ce projet le cas échéant (vide sinon)",
        max_length=1024,
        blank=True,
    )

    demarche_numerique_dossier_number = models.IntegerField(
        help_text=_("Dossier number on « Démarche numérique »"),
        blank=True,
        null=True,
        db_index=True,
    )

    demarche_numerique_dossier_id = models.CharField(
        help_text=_("Dossier ID on « Démarche numérique »"), blank=True, null=True
    )

    demarche_numerique_prefill_url = models.URLField(
        help_text=_(
            "Prefill dossier url on « Démarche numérique », used only when dossier is draft"
        ),
        blank=True,
        null=True,
    )

    demarche_numerique_state = models.CharField(
        _("State of the dossier on « Démarche numérique »"),
        max_length=20,
        choices=DOSSIER_STATES,
        default=DOSSIER_STATES.draft,
        db_index=True,
    )

    demarche_numerique_date_depot = models.DateTimeField(
        "Date de dépôt dans « Démarche numérique »",
        null=True,
        blank=True,
        db_index=True,
    )

    demarche_numerique_raw_dossier = models.JSONField(
        "Données brutes du dossier provenant de demarche.numerique.gouv.fr",
        default=dict,
        blank=True,
    )

    demarche_numerique_last_sync = models.DateTimeField(
        "Date de la dernière synchronisation avec demarche.numerique.gouv.fr",
        null=True,
        blank=True,
    )

    dn_archive = models.FileField(
        "Archive Démarches numériques",
        null=True,
        blank=True,
        upload_to=dn_archive_file_format,
    )

    instructor_free_mention = models.TextField(
        "Mention libre de l'instructeur", blank=True
    )

    instructor_private_mention = models.TextField(
        "Notes privées de l'instructeur", blank=True
    )

    followed_by = models.ManyToManyField(
        "users.User",
        related_name="followed_petition_projects",
        blank=True,
        verbose_name="Instructeurs suivant le projet",
    )
    latest_petitioner_msg = models.DateTimeField(
        verbose_name="Date du dernier message pétitionnaire",
        null=True,
        blank=True,
        default=None,
    )

    stage = models.CharField(
        "Étape",
        help_text="Ce champ est mis à jour automatiquement à la création des StatusLogs",
        max_length=30,
        choices=STAGES,
        default=STAGES.to_be_processed,
    )
    decision = models.CharField(
        "Décision",
        help_text="Ce champ est mis à jour automatiquement à la création des StatusLogs",
        max_length=30,
        choices=DECISIONS,
        default=DECISIONS.unset,
    )

    is_additional_information_requested = models.BooleanField(
        "En attente d'informations complémentaires ?",
        help_text="Mis à jour par les étapes de l'instruction.",
        default=False,
    )

    due_date = models.DateField(
        "Date de prochaine échéance",
        help_text="Mis à jour par les étapes de l'instruction.",
        null=True,
        blank=True,
    )
    silence_rule = models.CharField(
        "Règle du silence de l’administration",
        help_text="Règle en vigueur uniquement. Mise à jour par les étapes de l'instruction.",
        max_length=16,
        choices=SilenceRule.choices,
        null=True,
        blank=True,
    )
    silence_deadline = models.DateField(
        "Date à laquelle la règle du silence s’applique",
        help_text="Délai en cours uniquement. Mis à jour par les étapes de l'instruction.",
        null=True,
        blank=True,
    )

    # Meta fields
    created_at = models.DateTimeField(
        _("Date created"), default=timezone.now, db_index=True
    )

    class Meta:
        verbose_name = "Dossier"
        verbose_name_plural = "Dossiers"
        indexes = [
            models.Index(
                fields=[
                    "demarche_numerique_state",
                    "demarche_numerique_date_depot",
                ],
                name="pp_state_datedepot_idx",
            ),
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        moulinette_changed = not self.pk or self.tracker.has_changed("moulinette_url")

        # Set department code before saving
        if not self.department:
            department_code = self.get_department_code()
            try:
                self.department = Department.objects.defer("geometry").get(
                    department=department_code
                )
            except ObjectDoesNotExist:
                self.department = None
        super().save(*args, **kwargs)

        # Create a result snapshot
        if moulinette_changed:
            transaction.on_commit(
                lambda: ResultSnapshot.create_for_project(project=self)
            )

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self.clear_cached_properties()

    def clear_cached_properties(self):
        """Forget every cached property, so each one is recomputed from the current fields."""
        for name, attribute in inspect.getmembers(type(self)):
            if isinstance(attribute, cached_property):
                self.__dict__.pop(name, None)

    @property
    def is_closed(self):
        return self.stage == STAGES.closed

    @property
    def can_switch_to_authorization(self):
        """An RU dossier still in its declaration phase can switch to authorization."""
        return self.is_regime_unique() and self.stage in (
            STAGES.to_be_processed,
            STAGES.instruction_d,
        )

    @property
    def prefectural_order_log(self):
        """Get the latest status log carrying a prefectural order, if any.

        Each closing with an uploaded order creates a new log entry, so the
        latest one is the order currently in force.
        """
        return (
            self.status_history.exclude(prefectural_order="")
            .order_by("-created_at")
            .first()
        )

    def silence_rule_in(self, stage) -> SilenceRule | None:
        """What the administration's silence means for this dossier in `stage`.

        None outside the régime unique, or for a stage without a silence rule.
        """
        rule = None
        if self.is_regime_unique():
            rule = SILENCE_RULE_BY_INSTRUCTION_STAGE.get(stage)
        return rule

    @cached_property
    def latest_suspension(self):
        """Get the latest suspension log."""
        return self.status_history.filter(type=LOG_TYPES.suspension).first()

    def get_department_code(self):
        """Get department from moulinette url"""
        return extract_param_from_url(self.moulinette_url, "department")

    def get_log_event_data(self):
        """Get log event data for analytics"""
        data = {
            "reference": self.reference,
            "department": self.get_department_code(),
        }
        if self.hedge_data:
            data.update(self.hedge_data.get_statistics())

        return data

    @property
    def is_dossier_submitted(self):
        return self.demarche_numerique_state not in UNSUBMITTED_DOSSIER_STATES

    def synchronize_with_demarche_numerique(self, fetched_dossier: dict):
        """Refresh the project's cached « Démarche numérique » data and react to the dossier's state change.

        Discards unsaved changes on the instance. Alerts and emails go out once the transaction commits.
        """
        logger.info(f"Synchronizing file {self.reference} with « Démarche numérique »")

        with transaction.atomic():
            # Prevents overlapping syncs from acting on a stale copy.
            self.reload_with_lock()
            if self.has_newer_cached_dossier(fetched_dossier):
                logger.info(
                    f"Skipping a stale « Démarche numérique » copy of {self.reference}"
                )
                return

            is_submission = not self.is_dossier_submitted
            changed_outside = fetched_dossier["state"] != self.demarche_numerique_state

            # The dépôt's instruction events mirror the state « Démarche numérique » already holds.
            self.update_demarche_numerique_cache(fetched_dossier)

            if is_submission:
                self.record_submission(fetched_dossier)
            elif changed_outside:
                self.schedule_outside_change_alert(fetched_dossier)

            self.save()

    def reload_with_lock(self):
        """Reload the project from its row, locked until the transaction ends."""
        self.refresh_from_db(from_queryset=PetitionProject.objects.select_for_update())

    def has_newer_cached_dossier(self, fetched_dossier: dict) -> bool:
        """Whether the cached dossier was modified after the fetched one."""
        cached_at = read_last_modification(self.demarche_numerique_raw_dossier)
        fetched_at = read_last_modification(fetched_dossier)
        return bool(cached_at and fetched_at and cached_at > fetched_at)

    def update_cache_after_guichet_state_change(self, fetched_dossier: dict):
        """Cache the dossier « Démarche numérique » returned for a state change made from the guichet."""
        with transaction.atomic():
            self.reload_with_lock()
            self.update_demarche_numerique_cache(fetched_dossier)
            self.save()

    def record_submission(self, fetched_dossier: dict):
        """Apply the dépôt of the dossier to the project."""
        submission_date = read_submission_date(fetched_dossier)
        self.pin_simulation_date(submission_date)

        # Some démarches open a dossier straight into instruction on dépôt.
        if (
            fetched_dossier["state"] == DOSSIER_STATES.en_instruction
            and self.stage == STAGES.to_be_processed
        ):
            self.start_instruction(submission_date=submission_date)

        log_dossier_submission_event(self)
        self.schedule_submission_alert(fetched_dossier)
        self.schedule_submission_messages(submission_date)

    def schedule_submission_messages(self, submission_date: date):
        """Queue the GUH mailbox email and, for a déclaration, the applicant's receipt."""
        self.schedule_new_dossier_email()

        # The delay starts at the dépôt, even if « Démarche numérique » leaves the dossier en construction.
        if self.is_regime_unique():
            self.schedule_declaration_receipt(
                submission_date, declaration_due_date(submission_date)
            )

    def update_demarche_numerique_cache(self, fetched_dossier: dict):
        """Copy the fetched « Démarche numérique » dossier into the project's cached fields.

        The cached dossier may lack messages, so reading messages requires a forced fetch.
        """
        self.demarche_numerique_dossier_id = fetched_dossier["id"]
        self.demarche_numerique_state = fetched_dossier["state"]
        if fetched_dossier.get("dateDepot"):
            self.demarche_numerique_date_depot = parser.isoparse(
                fetched_dossier["dateDepot"]
            )

        self.demarche_numerique_raw_dossier = fetched_dossier
        self.clear_cached_properties()

        # Dossiers fetched without messages keep the previous date.
        if "messages" in fetched_dossier:
            dossier = Dossier.from_dict(fetched_dossier)
            self.latest_petitioner_msg = dossier.latest_applicant_message_date

        self.demarche_numerique_last_sync = timezone.now()

    def pin_simulation_date(self, submission_date: date):
        """Evaluate the project and its simulations with the rules in force on `submission_date`."""
        date_param = {"date": submission_date.isoformat()}
        self.moulinette_url = update_qs(self.moulinette_url, date_param)
        self.clear_cached_properties()

        simulations = list(self.simulations.all())
        for simulation in simulations:
            simulation.moulinette_url = update_qs(simulation.moulinette_url, date_param)
        Simulation.objects.bulk_update(simulations, ["moulinette_url"])

    def schedule_submission_alert(self, fetched_dossier: dict):
        """Queue the team alert announcing the dépôt, for after commit."""
        # Imported here: the tasks module imports this one.
        from envergo.petitions.tasks import send_team_alert_async

        alert = dossier_submission_alert(self, fetched_dossier)
        transaction.on_commit(lambda: send_team_alert_async.delay(alert), robust=True)

    def schedule_outside_change_alert(self, fetched_dossier: dict):
        """Queue the team alert reporting a state change made outside the guichet, for after commit."""
        # Imported here: the tasks module imports this one.
        from envergo.petitions.tasks import send_team_alert_async

        alert = dossier_state_changed_outside_guh_alert(self, fetched_dossier)
        transaction.on_commit(lambda: send_team_alert_async.delay(alert), robust=True)

    def schedule_new_dossier_email(self):
        """Queue the GUH mailbox email for after commit, so a mail failure blocks nothing."""
        # Imported here: the tasks module imports this one.
        from envergo.petitions.tasks import send_new_dossier_email_async

        transaction.on_commit(
            lambda: send_new_dossier_email_async.delay(self.pk), robust=True
        )

    def schedule_declaration_receipt(self, received_on, due_date):
        """Queue the déclaration receipt for after commit, so a DN failure blocks nothing."""
        # Imported here: the tasks module imports this one.
        from envergo.petitions.tasks import send_declaration_receipt_async

        received_on_iso = received_on.isoformat()
        due_date_iso = due_date.isoformat()

        transaction.on_commit(
            lambda: send_declaration_receipt_async.delay(
                self.pk, received_on_iso, due_date_iso
            ),
            robust=True,
        )

    def get_moulinette(self):
        """Recreate moulinette from moulinette url and hedge data"""
        return self.moulinette

    @cached_property
    def moulinette(self):
        moulinette_data = self._parse_moulinette_data()
        moulinette_data["haies"] = self.hedge_data
        form_data = {"initial": moulinette_data, "data": moulinette_data}
        return MoulinetteHaie(form_data)

    def get_triage_form(self):
        """Recreate triage form from moulinette url"""
        moulinette_data = self._parse_moulinette_data()
        return TriageFormHaie(data=moulinette_data)

    def _parse_moulinette_data(self):
        parsed_url = urlparse(self.moulinette_url)
        query_string = parsed_url.query
        # We need to convert the query string to a flat dict
        raw_data = QueryDict(query_string)
        moulinette_data = raw_data.dict()
        return moulinette_data

    @cached_property
    def moulinette_data(self):
        data = self._parse_moulinette_data()
        # use the HedgeData object instead of the uuid to emulate a form like behavior usually used by the moulinette
        data["haies"] = self.hedge_data
        return data

    def has_view_permission(self, user):
        """User has view permission on project, according to
        - superuser
        - user with access haie and invitation token
        - user with access haie and right to project department
        """
        if not user.is_authenticated:
            return False

        return user.is_superuser or (
            user.has_instruction_access
            and (
                self.department_id in user.department_ids
                or user.invitation_tokens.filter(petition_project_id=self.pk).exists()
            )
        )

    def has_change_permission(self, user):
        """User has edit permission on project, according to
        - superuser
        - user with access haie, is coordinator for department
        """
        if not user.is_authenticated:
            return False

        return user.is_superuser or (
            user.has_coordination_access and self.department_id in user.department_ids
        )

    @property
    def demarche_numerique_petitioner_url(self) -> str | None:
        """
        Returns the URL of the dossier for the petitioner.
        """
        if self.demarche_numerique_dossier_number:
            return (
                f"{settings.DEMARCHE_NUMERIQUE['DOSSIER_BASE_URL']}/dossiers/"
                f"{self.demarche_numerique_dossier_number}/"
            )
        return None

    @property
    def demarche_numerique_petitioner_messaging_url(self) -> str | None:
        """
        Returns the URL of the dossier messaging for the petitioner.
        """
        if self.demarche_numerique_petitioner_url:
            return f"{self.demarche_numerique_petitioner_url}messagerie"
        return None

    def get_demarche_numerique_instructor_url(self, demarche_number) -> str | None:
        """
        Returns the URL of the dossier for the instructor.
        """
        if self.demarche_numerique_dossier_number:
            return (
                f"{settings.DEMARCHE_NUMERIQUE['DOSSIER_BASE_URL']}/procedures/{demarche_number}/dossiers/"
                f"{self.demarche_numerique_dossier_number}/"
            )
        return None

    @cached_property
    def prefetched_dossier(self) -> Dossier | None:
        """Returns the dossier from Démarche numérique if it has been fetched before."""
        dossier_as_dict = self.demarche_numerique_raw_dossier
        return Dossier.from_dict(dossier_as_dict) if dossier_as_dict else None

    @property
    def has_unread_messages(self):
        """Check if the current user has received unread messages.

        Note: the `latest_access` property MUST be added with an annotation
        in the queryset
        """

        has_unread_messages = (
            self.latest_petitioner_msg is not None
            and self.latest_access is not None
            and self.latest_access < self.latest_petitioner_msg
        )
        return has_unread_messages

    def get_available_regulations(self):
        return Regulation.objects.filter(
            regulation__in=self.config.regulations_available
        ).order_by("weight")

    @property
    def category(self):
        return HedgeCategory(self._category)

    @category.setter
    def category(self, value):
        if not isinstance(value, HedgeCategory):
            raise ValueError("Category must be an instance of HedgeCategory")

        self._category = value.value

    def is_regime_unique(self):
        return self.category == HedgeCategory.ru

    def is_declaration_instruction(self):
        """The dossier is in the RU declaration procedure."""
        return self.is_regime_unique() and self.stage == STAGES.instruction_d

    def is_authorization_instruction(self):
        """The dossier is in the RU authorization procedure."""
        return self.is_regime_unique() and self.stage == STAGES.instruction_a

    def is_emergency(self):
        return (
            self.is_regime_unique()
            and self.moulinette_data.get("urgence", None) == "oui"
        )

    @property
    def needs_demarche_numerique_sync(self):
        one_hour_ago = timezone.now() - timedelta(hours=1)
        return (
            not self.demarche_numerique_raw_dossier
            or self.demarche_numerique_last_sync is not None
            and self.demarche_numerique_last_sync < one_hour_ago
        )

    @cached_property
    def demarche_numerique_dossier(self):
        if self.needs_demarche_numerique_sync:
            raise DossierNotSynchronized(
                "Project must be synchronized before accessing demarche numérique dossier"
            )

        dossier = Dossier.from_dict(self.demarche_numerique_raw_dossier)
        return dossier


USER_TYPE = Choices(
    ("petitioner", "Demandeur"),
    ("instructor", "Instructeur"),
)


class Simulation(models.Model):
    """A single alternative set of simulation parameters for a given project."""

    project = models.ForeignKey(
        PetitionProject,
        verbose_name="Simulation",
        on_delete=models.CASCADE,
        related_name="simulations",
    )
    is_initial = models.BooleanField("Initiale ?", default=False)
    is_active = models.BooleanField("Active ?", default=False)
    moulinette_url = models.URLField(_("Moulinette url"), max_length=2048)
    source = models.CharField("Auteur", choices=USER_TYPE, default=USER_TYPE.petitioner)
    comment = models.TextField("Commentaire")

    created_at = models.DateTimeField(_("Date created"), default=timezone.now)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        verbose_name=_("Created by"),
        null=True,
    )

    class Meta:
        verbose_name = "Simulation alternative"
        verbose_name_plural = "Simulations alternatives"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "is_active"],
                condition=Q(is_active=True),
                name="single_active_simulation",
            ),
            models.UniqueConstraint(
                fields=["project", "is_initial"],
                condition=Q(is_initial=True),
                name="single_initial_simulation",
            ),
        ]

    def can_be_deleted(self):
        return not (self.is_initial or self.is_active)

    def can_be_activated(self):
        return not self.project.is_closed

    def custom_url(self, view_name, **kwargs):
        """Generate an url with the given parameters."""

        m_url = MoulinetteUrl(self.moulinette_url)
        qt = m_url.querydict
        # Use iteration instead of `qt.update` because qt is a MultiValueDict and
        # update just adds more values instead of just updating them
        for key, value in kwargs.items():
            qt[key] = value
        f_url = reverse(view_name)
        url = f"{f_url}?{qt.urlencode()}"
        return url

    @property
    def form_url(self):
        """Return the moulinette form url with the simulation parameters."""
        return self.custom_url(
            "moulinette_form", project_reference=self.project.reference
        )

    @property
    def result_url(self):
        """Return the result form url with the simulation parameters."""

        if self.is_active:
            url = reverse("petition_project", args=[self.project.reference])
        else:
            url = self.custom_url(
                "moulinette_result_plantation", project_reference=self.project.reference
            )
        return url


def one_month_from_now():
    return timezone.now() + timedelta(days=30)


def generate_token():
    return secrets.token_urlsafe(32)


class InvitationToken(models.Model):
    """A token used to invite a user to join a petition project."""

    token = models.CharField(
        "Jeton", max_length=64, unique=True, default=generate_token
    )
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        verbose_name="Compte invitant",
    )
    petition_project = models.ForeignKey(
        PetitionProject,
        on_delete=models.CASCADE,
        related_name="invitation_tokens",
        verbose_name="Projet",
    )
    valid_until = models.DateTimeField(
        "Valide jusqu'au",
        help_text="Date d'expiration du jeton",
        null=True,
        blank=True,
        default=one_month_from_now,
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="invitation_tokens",
        verbose_name="Compte invité",
    )

    # Meta fields
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = "Jeton d'invitation"
        verbose_name_plural = "Jetons d'invitation"

    def is_valid(self, user):
        """Check if the token is still valid."""

        return all(
            (
                self.user_id is None,
                self.created_by != user,
                self.valid_until >= timezone.now(),
            )
        )


# Some data constraints checks

# Check that all request for info suspension data is set
q_suspended = Q(type=LOG_TYPES.suspension) & Q(due_date__isnull=False)

# Check that no single field is set
q_not_suspended = (
    Q(type=LOG_TYPES.status_change)
    & Q(original_due_date__isnull=True)
    & Q(info_receipt_date__isnull=True)
)

# Check that the receipt date is only set if the project is resumed
q_resumed = Q(type=LOG_TYPES.resumption) & Q(info_receipt_date__isnull=False)


class StatusLog(models.Model):
    """A petition project status log entry.

    Each entry represents one of:
    - status_change: A change in stage and/or decision
    - suspension: A request for additional information (pauses the process)
    - resumption: Receipt of additional information (resumes the process)
    """

    petition_project = models.ForeignKey(
        PetitionProject,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name="Projet",
    )
    type = models.CharField(
        "Type de log",
        max_length=20,
        choices=LOG_TYPES,
        default=LOG_TYPES.status_change,
    )
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        verbose_name=_("Created by"),
        null=True,
    )
    stage = models.CharField(
        "Étape",
        max_length=30,
        choices=STAGES,
        default=STAGES.to_be_processed,
    )
    decision = models.CharField(
        "Décision",
        max_length=30,
        choices=DECISIONS,
        default=DECISIONS.unset,
    )
    update_comment = models.TextField(
        "Commentaire interne",
        help_text="Ajouter un commentaire expliquant le contexte du changement.",
        blank=True,
    )
    status_date = models.DateField(
        "Date effective du changement",
        help_text="Par défaut, la date du jour. Il est possible de choisir une date passée si le changement est "
        "rétroactif.",
        default=timezone.now,
    )
    prefectural_order = models.FileField(
        "Document de décision",
        upload_to=prefectural_order_file_format,
        blank=True,
    )
    applicant_message = models.TextField(
        "Message au demandeur",
        blank=True,
        default="",
    )
    due_date = models.DateField(
        "Date de prochaine échéance",
        null=True,
        blank=True,
    )
    agreement_deadline = models.DateField(
        "Date à laquelle le silence vaut accord",
        help_text="Sans réponse de l’administration à cette date, l’accord tacite est acquis.",
        null=True,
        blank=True,
    )
    refusal_deadline = models.DateField(
        "Date limite au-delà de laquelle le silence vaut refus",
        help_text="Passé cette date, le silence gardé par l’administration vaudra refus.<br>"
        "La présence de cette date est obligatoire dans la notification de bascule en autorisation.<br>"
        "Elle doit être au moins deux mois après aujourd'hui.",
        null=True,
        blank=True,
    )

    # "Request for additional information" related fields
    original_due_date = models.DateField(
        "Date de prochaine échéance avant suspension", null=True, blank=True
    )
    info_receipt_date = models.DateField(
        "Date de réception des pièces complémentaires", null=True, blank=True
    )

    # Meta fields
    created_at = models.DateTimeField(
        "Date de saisie du changement de statut", default=timezone.now
    )

    class Meta:
        verbose_name = "Log de changement de statut de projet"
        verbose_name_plural = "Historique des changements de statut de projet"
        constraints = [
            models.CheckConstraint(
                condition=~(Q(stage=STAGES.closed) & Q(decision=DECISIONS.unset)),
                name="forbid_closed_with_unset_decision",
            ),
            models.CheckConstraint(
                condition=q_suspended | q_not_suspended | q_resumed,
                name="suspension_data_is_consistent",
            ),
        ]
        ordering = ["-created_at"]


class LatestMessagerieAccess(models.Model):
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        verbose_name="Accès par",
        related_name="messagerie_accesses",
    )
    project = models.ForeignKey(
        PetitionProject,
        on_delete=models.CASCADE,
        verbose_name="Projet",
        related_name="messagerie_accesses",
    )
    access = models.DateTimeField("Dernier accès messagerie", default=timezone.now)

    class Meta:
        verbose_name = "Dernier accès messagerie"
        verbose_name_plural = "Derniers accès messagerie"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project"], name="access_unique_constraint"
            )
        ]


class ResultSnapshot(ResultSnapshotBase):
    """Snapshot of moulinette results for a PetitionProject."""

    project = models.ForeignKey(
        PetitionProject,
        on_delete=models.CASCADE,
        related_name="result_snapshots",
        verbose_name="Projet",
    )

    @classmethod
    def create_for_project(cls, project):
        """Create a snapshot for a PetitionProject."""
        moulinette = project.get_moulinette()
        payload = moulinette.summary()
        # Convert HedgeData object to its UUID for JSON serialization
        payload["haies"] = payload["haies"].id
        return cls.objects.create(
            project=project,
            moulinette_url=project.moulinette_url,
            payload=payload,
        )
