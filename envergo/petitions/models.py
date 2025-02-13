from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from envergo.evaluations.models import generate_reference
from envergo.hedges.models import HedgeData
from envergo.utils.urls import extract_param_from_url

DOSSIER_STATES = Choices(
    ("draft", _("Draft")),
    ("prefilled", _("Prefilled")),
    ("accepte", _("Accepted")),
    ("en_construction", _("Under construction")),
    ("en_instruction", _("Under instruction")),
    ("refuse", _("Refused")),
    ("sans_suite", _("No follow-up")),
)


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
