import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from dateutil import parser
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.http import QueryDict
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from envergo.analytics.models import Event
from envergo.analytics.utils import log_event_raw
from envergo.evaluations.models import generate_reference
from envergo.geodata.models import DEPARTMENT_CHOICES, Department
from envergo.hedges.models import HedgeData
from envergo.moulinette.forms import TriageFormHaie
from envergo.moulinette.models import MoulinetteHaie
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
    )

    hedge_data = models.ForeignKey(
        HedgeData,
        on_delete=models.PROTECT,
    )

    demarches_simplifiees_dossier_number = models.IntegerField(
        help_text=_("Dossier number on demarches-simplifiees.fr"), blank=True, null=True
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
        logger.info(f"Synchronizing file {self.reference} with DS")

        if not self.is_dossier_submitted:
            # first time we have some data about this dossier

            demarche_name = (
                dossier["demarche"]["title"]
                if "demarche" in dossier and "title" in dossier["demarche"]
                else "Nom inconnu"
            )
            demarche_number = (
                dossier["demarche"]["number"]
                if "demarche" in dossier and "number" in dossier["demarche"]
                else "Numéro inconnu"
            )
            demarche_label = f"la démarche n°{demarche_number} ({demarche_name})"

            ds_url = self.get_demarches_simplifiees_instructor_url(demarche_number)

            department = extract_param_from_url(self.moulinette_url, "department")
            admin_url = reverse(
                "admin:petitions_petitionproject_change",
                args=[self.pk],
            )

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
                    "demarche_label": demarche_label,
                    "ds_url": ds_url,
                    "admin_url": f"https://{haie_site.domain}{admin_url}",
                    "usager_email": usager_email,
                    "length_to_remove": self.hedge_data.length_to_remove(),
                },
            )
            notify(message_body, "haie")

            creation_event = (
                Event.objects.order_by("-date_created")
                .filter(
                    metadata__reference=self.reference,
                    category="dossier",
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
                "dossier",
                "depot",
                visitor_id,
                user,
                haie_site,
                **self.get_log_event_data(),
            )

        self.demarches_simplifiees_state = dossier["state"]
        if "dateDepot" in dossier and dossier["dateDepot"]:
            self.demarches_simplifiees_date_depot = parser.isoparse(
                dossier["dateDepot"]
            )

        self.demarches_simplifiees_raw_dossier = dossier

        self.demarches_simplifiees_last_sync = datetime.now(timezone.utc)
        self.save()

    def get_moulinette(self):
        """Recreate moulinette from moulinette url and hedge data"""
        moulinette_data = self._parse_moulinette_data()
        moulinette_data["haies"] = self.hedge_data
        moulinette = MoulinetteHaie(
            moulinette_data,
            moulinette_data,
            False,
        )
        return moulinette

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

    def has_user_as_department_instructor(self, user):
        department = self.department
        return user.is_superuser or all(
            (
                user.is_active,
                user.access_haie,
                user.departments.filter(id=department.id).exists(),
            )
        )

    def has_user_as_invited_instructor(self, user):
        return user.is_superuser or all(
            (
                user.is_active,
                user.access_haie,
                user.invitation_tokens.filter(petition_project_id=self.pk).exists(),
            )
        )

    def has_user_as_instructor(self, user):
        return self.has_user_as_invited_instructor(
            user
        ) or self.has_user_as_department_instructor(user)

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
        verbose_name="Utilisateur invité",
    )

    # Meta fields
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = "Jeton d'invitation"
        verbose_name_plural = "Jetons d'invitation"

    def is_valid(self):
        """Check if the token is still valid."""
        return self.user_id is None and self.valid_until >= timezone.now()
