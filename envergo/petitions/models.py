import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from dateutil import parser
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.http import QueryDict
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from envergo.analytics.models import Event
from envergo.analytics.utils import log_event_raw
from envergo.evaluations.models import generate_reference
from envergo.geodata.models import DEPARTMENT_CHOICES, Department
from envergo.hedges.models import HedgeData
from envergo.moulinette.forms import TriageFormHaie
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.utils import MoulinetteUrl
from envergo.petitions.demarches_simplifiees.models import Dossier
from envergo.users.models import User
from envergo.utils.mattermost import notify
from envergo.utils.urls import extract_param_from_url

logger = logging.getLogger(__name__)

DOSSIER_STATES = Choices(
    ("draft", _("Draft")),
    ("prefilled", _("Prefilled")),
    ("accepte", _("Accepted")),
    ("en_construction", _("Under construction")),
    ("en_instruction", _("Under instruction")),
    ("refuse", _("Refused")),
    ("sans_suite", _("No follow-up")),
)

STAGES = Choices(
    ("to_be_processed", "À instruire"),
    ("instruction_d", "Instruction déclaration"),
    ("instruction_a", "Instruction autorisation"),
    ("instruction_h", "Instruction hors régime unique"),
    ("preparing_decision", "Rédaction décision"),
    ("notification", "Notification / Publicité"),
    ("closed", "Dossier clos"),
)

DECISIONS = Choices(
    ("unset", "À déterminer"),
    ("tacit_agreement", "Accord tacite"),
    ("express_agreement", "Accord exprès"),
    ("opposition", "Opposition"),
    ("dropped", "Classé sans suite"),
)

# This session key is used when we are not able to find the real user session key.
SESSION_KEY = "untracked_dossier_submission"


class PetitionProject(models.Model):
    """A petition project by a project owner.

    A petition project will store any data needed to follow up a request concerning a hedge.
    Both the project owner and the public administration will be able to follow up the request.
    """

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

    demarches_simplifiees_dossier_number = models.IntegerField(
        help_text=_("Dossier number on demarches-simplifiees.fr"), blank=True, null=True
    )

    demarches_simplifiees_dossier_id = models.CharField(
        help_text=_("Dossier ID on demarches-simplifiees.fr"), blank=True, null=True
    )

    demarches_simplifiees_state = models.CharField(
        _("State of the dossier on demarches-simplifiees.fr"),
        max_length=20,
        choices=DOSSIER_STATES,
        default=DOSSIER_STATES.draft,
    )

    demarches_simplifiees_date_depot = models.DateTimeField(
        "Date de dépôt dans Démarches Simplifiées", null=True, blank=True
    )

    demarches_simplifiees_raw_dossier = models.JSONField(
        "Données brutes du dossier provenant de Démarches Simplifiées",
        default=dict,
        blank=True,
    )

    demarches_simplifiees_last_sync = models.DateTimeField(
        "Date de la dernière synchronisation avec Démarches Simplifiées",
        null=True,
        blank=True,
    )

    onagre_number = models.CharField(
        "Référence ONAGRE du dossier", max_length=64, blank=True
    )

    instructor_free_mention = models.TextField(
        "Mention libre de l'instructeur", blank=True
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

    # Meta fields
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Petition project")
        verbose_name_plural = _("Petition projects")

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        """Set department code before saving"""
        if not self.department:
            department_code = self.get_department_code()
            try:
                self.department = Department.objects.defer("geometry").get(
                    department=department_code
                )
            except ObjectDoesNotExist:
                self.department = None
        super().save(*args, **kwargs)

    @cached_property
    def current_status(self):
        # Make sure the `status_history` is prefetched with the correct ordering
        log = self.status_history.first()
        return log

    @property
    def current_stage(self):
        return (
            self.current_status.stage if self.current_status else STAGES.to_be_processed
        )

    @property
    def current_decision(self):
        return self.current_status.decision if self.current_status else DECISIONS.unset

    @property
    def due_date(self):
        return self.current_status.due_date if self.current_status else None

    @property
    def is_paused(self):
        return self.current_status.is_paused if self.current_status else False

    def get_department_code(self):
        """Get department from moulinette url"""
        return extract_param_from_url(self.moulinette_url, "department")

    def get_log_event_data(self):
        """Get log event data for analytics"""
        hedge_centroid_coords = self.hedge_data.get_centroid_to_remove()
        return {
            "reference": self.reference,
            "department": self.get_department_code(),
            "longueur_detruite": (
                self.hedge_data.length_to_remove() if self.hedge_data else None
            ),
            "longueur_plantee": (
                self.hedge_data.length_to_plant() if self.hedge_data else None
            ),
            "lnglat_centroide_haie_detruite": (
                f"{hedge_centroid_coords.x}, {hedge_centroid_coords.y}"
            ),
            "dept_haie_detruite": self.hedge_data.get_department(),
        }

    @property
    def is_dossier_submitted(self):
        return (
            self.demarches_simplifiees_state != DOSSIER_STATES.draft
            and self.demarches_simplifiees_state != DOSSIER_STATES.prefilled
        )

    def synchronize_with_demarches_simplifiees(self, dossier: dict):
        """Update the petition project with the latest data from demarches-simplifiees.fr

        a notification is sent to the mattermost channel when the dossier is submitted for the first time
        """

        def get_admin_url():
            return reverse(
                "admin:petitions_petitionproject_change",
                args=[self.pk],
            )

        def get_instructor_url():
            return reverse(
                "petition_project_instructor_view", kwargs={"reference": self.reference}
            )

        def get_ds_url():
            demarche_number = (
                dossier["demarche"]["number"]
                if "demarche" in dossier and "number" in dossier["demarche"]
                else "Numéro inconnu"
            )

            return self.get_demarches_simplifiees_instructor_url(demarche_number)

        def get_latest_petitioner_msg():
            emails = [instructeur["email"] for instructeur in dossier["instructeurs"]]
            dates = sorted(
                [
                    datetime.fromisoformat(msg["createdAt"])
                    for msg in dossier["messages"]
                    if msg["email"] in emails
                ],
                reverse=True,
            )
            return dates[0] if len(dates) else None

        logger.info(f"Synchronizing file {self.reference} with DS")

        if not self.is_dossier_submitted:
            # first time we have some data about this dossier
            department = extract_param_from_url(self.moulinette_url, "department")
            usager_email = (
                dossier["usager"]["email"]
                if "usager" in dossier and "email" in dossier["usager"]
                else "non renseigné"
            )
            haie_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)

            message_body = render_to_string(
                "haie/petitions/mattermost_dossier_submission_notif.txt",
                context={
                    "department": dict(DEPARTMENT_CHOICES).get(department, department),
                    "dossier_number": self.demarches_simplifiees_dossier_number,
                    "instructor_url": f"https://{haie_site.domain}{get_instructor_url()}",
                    "ds_url": get_ds_url(),
                    "admin_url": f"https://{haie_site.domain}{get_admin_url()}",
                    "usager_email": usager_email,
                    "length_to_remove": self.hedge_data.length_to_remove(),
                },
            )
            notify(message_body, "haie")

            creation_event = (
                Event.objects.order_by("-date_created")
                .filter(
                    metadata__reference=self.reference,
                    category="demande",
                    event="creation",
                )
                .first()
            )
            if not creation_event:
                logger.warning(
                    f"Unable to find creation event for project {self.reference}. "
                    f"The submission event will be logged with a mocked session key.",
                    extra={
                        "project": self,
                        "session_key": SESSION_KEY,
                    },
                )

            visitor_id = creation_event.session_key if creation_event else SESSION_KEY

            user = User(is_staff=False)

            log_event_raw(
                "demande",
                "depot",
                visitor_id,
                user,
                haie_site,
                **self.get_log_event_data(),
            )
        elif (
            self.demarches_simplifiees_state
            and dossier["state"] != self.demarches_simplifiees_state
        ):
            # DS state have been changed outside of GUH. We are trying to prevent this. Notify admin
            department = extract_param_from_url(self.moulinette_url, "department")
            haie_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)

            message_body = render_to_string(
                "haie/petitions/mattermost_dossier_state_updated_outside_of_guh.txt",
                context={
                    "department": dict(DEPARTMENT_CHOICES).get(department, department),
                    "instructor_url": f"https://{haie_site.domain}{get_instructor_url()}",
                    "ds_url": get_ds_url(),
                    "admin_url": f"https://{haie_site.domain}{get_admin_url()}",
                },
            )
            notify(message_body, "haie")

        self.demarches_simplifiees_dossier_id = dossier["id"]
        self.demarches_simplifiees_state = dossier["state"]
        if "dateDepot" in dossier and dossier["dateDepot"]:
            self.demarches_simplifiees_date_depot = parser.isoparse(
                dossier["dateDepot"]
            )

        self.demarches_simplifiees_raw_dossier = dossier

        if "instructeurs" in dossier and "messages" in dossier:
            self.latest_petitioner_msg = get_latest_petitioner_msg()

        self.demarches_simplifiees_last_sync = datetime.now(timezone.utc)
        self.save()

    def get_moulinette(self):
        """Recreate moulinette from moulinette url and hedge data"""
        if not hasattr(self, "_moulinette"):
            moulinette_data = self._parse_moulinette_data()
            moulinette_data["haies"] = self.hedge_data
            form_data = {"initial": moulinette_data, "data": moulinette_data}
            self._moulinette = MoulinetteHaie(form_data)
        return self._moulinette

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

    def has_view_permission(self, user):
        """User has view permission on project, according to
        - superuser
        - user with access haie and invitation token
        - user with access haie and right to project department
        """
        department = self.department
        return user.is_superuser or all(
            (
                user.is_active,
                user.access_haie,
                (
                    user.invitation_tokens.filter(petition_project_id=self.pk).exists()
                    or user.departments.filter(id=department.id).exists()
                ),
            )
        )

    def has_change_permission(self, user):
        """User has edit permission on project, according to
        - superuser
        - user with access haie, is instructor for department
        """
        department = self.department
        return user.is_superuser or all(
            (
                user.is_active,
                user.access_haie,
                user.is_instructor,
                user.departments.filter(id=department.id).exists(),
            )
        )

    @property
    def demarches_simplifiees_petitioner_url(self) -> str | None:
        """
        Returns the URL of the dossier for the petitioner.
        """
        if self.demarches_simplifiees_dossier_number:
            return (
                f"{settings.DEMARCHES_SIMPLIFIEES["DOSSIER_BASE_URL"]}/dossiers/"
                f"{self.demarches_simplifiees_dossier_number}/"
            )
        return None

    def get_demarches_simplifiees_instructor_url(self, demarche_number) -> str | None:
        """
        Returns the URL of the dossier for the instructor.
        """
        if self.demarches_simplifiees_dossier_number:
            return (
                f"{settings.DEMARCHES_SIMPLIFIEES["DOSSIER_BASE_URL"]}/procedures/{demarche_number}/dossiers/"
                f"{self.demarches_simplifiees_dossier_number}/"
            )
        return None

    @property
    def prefetched_dossier(self) -> Dossier | None:
        """Returns the dossier from demarches-simplifiees.fr if it has been fetched before."""
        dossier_as_dict = self.demarches_simplifiees_raw_dossier
        return Dossier.from_dict(dossier_as_dict) if dossier_as_dict else None

    @cached_property
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

    class Meta:
        verbose_name = "Simulation"
        verbose_name_plural = "Simulations"
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
        return not self.project.current_status.is_closed

    def custom_url(self, view_name, **kwargs):
        """Generate an url with the given parameters."""

        m_url = MoulinetteUrl(self.moulinette_url)
        qt = m_url.querydict
        qt.update(kwargs)
        f_url = reverse(view_name)
        url = f"{f_url}?{qt.urlencode()}"
        return url

    @property
    def form_url(self):
        """Return the moulinette form url with the simulation parameters."""
        return self.custom_url("moulinette_form", alternative=True)

    @property
    def result_url(self):
        """Return the result form url with the simulation parameters."""

        if self.is_active:
            url = reverse("petition_project", args=[self.project.reference])
        else:
            url = self.custom_url("moulinette_result_plantation", alternative=True)
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

    def is_valid(self):
        """Check if the token is still valid."""
        return self.user_id is None and self.valid_until >= timezone.now()


# Some data constraints checks

# Check that all request for info suspension data is set
q_suspended = Q(suspension_date__isnull=False) & Q(response_due_date__isnull=False)

# Check that no single field is set
q_not_suspended = (
    Q(suspension_date__isnull=True)
    & Q(response_due_date__isnull=True)
    & Q(original_due_date__isnull=True)
)

# Check that the receipt date is only set if the project was suspended
q_receipt_date = Q(info_receipt_date__isnull=True) | (
    Q(info_receipt_date__isnull=False) & q_suspended
)


class StatusLog(models.Model):
    """A petition project status (stage + decision) change log entry."""

    petition_project = models.ForeignKey(
        PetitionProject,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name="Projet",
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
        "Commentaire",
        help_text="Ajouter un commentaire expliquant le contexte du changement.",
        blank=True,
    )
    status_date = models.DateField(
        "Date effective du changement",
        help_text="Par défaut, la date du jour. Il est possible de choisir une date passée si le changement est "
        "rétroactif.",
        default=timezone.now,
    )
    due_date = models.DateField(
        "Date de prochaine échéance",
        null=True,
        blank=True,
    )

    # "Request for additional information" related fields
    suspension_date = models.DateField(
        "Date de suspension pour demande d'information complémentaire",
        null=True,
        blank=True,
    )
    response_due_date = models.DateField(
        "Échéance pour l'envoi de pièces complémentaires",
        null=True,
        blank=True,
    )
    original_due_date = models.DateField(
        "Date de prochaine échéance avant suspension", null=True, blank=True
    )
    suspended_by = models.ForeignKey(
        "users.User",
        related_name="suspended_logs",
        on_delete=models.SET_NULL,
        verbose_name="Auteur de la demande d'informations complémentaires",
        null=True,
    )
    info_receipt_date = models.DateField(
        "Date de réception des pièces complémentaires", null=True, blank=True
    )
    resumed_by = models.ForeignKey(
        "users.User",
        related_name="resumed_logs",
        on_delete=models.SET_NULL,
        verbose_name="Auteur de la reprise de la procédure suite à la réception d'informations complémentaires",
        null=True,
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
                check=~(Q(stage=STAGES.closed) & Q(decision=DECISIONS.unset)),
                name="forbid_closed_with_unset_decision",
            ),
            models.CheckConstraint(
                check=q_suspended | q_not_suspended,
                name="suspension_data_is_consistent",
            ),
            models.CheckConstraint(
                check=q_receipt_date, name="receipt_date_data_is_consistent"
            ),
        ]
        ordering = ["-created_at"]

    @property
    def is_paused(self):
        """Are we currently waiting for additional info?"""

        return self.suspension_date is not None and self.info_receipt_date is None

    @property
    def is_closed(self):
        return self.stage == STAGES.closed


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
