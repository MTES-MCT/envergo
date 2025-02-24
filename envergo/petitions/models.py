import logging

from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from envergo.analytics.utils import log_event_raw
from envergo.evaluations.models import generate_reference
from envergo.geodata.models import DEPARTMENT_CHOICES
from envergo.hedges.models import HedgeData
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

    # Meta fields
    created_at = models.DateTimeField(_("Date created"), default=timezone.now)

    class Meta:
        verbose_name = _("Petition project")
        verbose_name_plural = _("Petition projects")

    def __str__(self):
        return self.reference

    def get_log_event_data(self):
        department = extract_param_from_url(self.moulinette_url, "department")
        return {
            "reference": self.reference,
            "department": department,
            "longueur_detruite": (
                self.hedge_data.length_to_remove() if self.hedge_data else None
            ),
            "longueur_plantee": (
                self.hedge_data.length_to_plant() if self.hedge_data else None
            ),
        }

    @property
    def is_dossier_submitted(self):
        return (
            self.demarches_simplifiees_state != DOSSIER_STATES.draft
            and self.demarches_simplifiees_state != DOSSIER_STATES.prefilled
        )

    def synchronize_with_demarches_simplifiees(
        self, dossier, site, demarche_label, ds_url, visitor_id, user
    ):
        """update the petition project with the latest data from demarches-simplifiees.fr

        a notification is sent to the mattermost channel when the dossier is submitted for the first time
        """
        if not self.is_dossier_submitted:
            # first time we have some data about this dossier
            department = extract_param_from_url(self.moulinette_url, "department")
            admin_url = reverse(
                "admin:petitions_petitionproject_change",
                args=[self.pk],
            )

            usager_email = (dossier.get("usager") or {}).get("email", "non renseigné")
            message_body = render_to_string(
                "haie/petitions/mattermost_dossier_submission_notif.txt",
                context={
                    "department": dict(DEPARTMENT_CHOICES).get(department, department),
                    "demarche_label": demarche_label,
                    "ds_url": ds_url,
                    "admin_url": f"https://{site.domain}{admin_url}",
                    "usager_email": usager_email,
                    "length_to_remove": self.hedge_data.length_to_remove(),
                },
            )
            notify(message_body, "haie")

            log_event_raw(
                "dossier",
                "depot",
                visitor_id,
                user,
                site,
                **self.get_log_event_data(),
            )

        self.demarches_simplifiees_state = dossier["state"]
        self.save()
