import datetime
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import set_urlconf
from django.utils import timezone

from envergo.moulinette.models import ConfigHaie
from envergo.petitions.demarche_numerique.client import (
    DemarcheNumeriqueClient,
    DemarcheNumeriqueError,
)
from envergo.petitions.demarche_numerique.models import Dossier
from envergo.petitions.models import PetitionProject
from envergo.utils.tchap import notify

logger = logging.getLogger(__name__)

DOMAIN_BLACK_LIST = settings.DEMARCHE_NUMERIQUE["DOSSIER_DOMAIN_BLACK_LIST"]


class Command(BaseCommand):
    help = (
        "Fetch freshly submitted dossier on « Démarche numérique » and notify admins."
    )

    def handle(self, *args, **options):
        """Sync the dossiers recently updated on « Démarche numérique »."""

        if not settings.DEMARCHE_NUMERIQUE["ENABLED"]:
            logger.warning("« Démarche numérique » is not enabled. Doing nothing.")
            return None

        set_urlconf("config.urls_haie")
        try:
            self.synchronize_recent_dossiers()
        finally:
            set_urlconf(None)

    def synchronize_recent_dossiers(self):
        """Sync the recently updated dossiers of every démarche."""
        now_utc = datetime.datetime.now(datetime.UTC)
        # NB: if you change this timedelta, you should also change the cron job frequency
        # The cron job is run every hour.
        # We fetch the updates from the last 2 hours to be sure as we may have some delay in the cron job execution
        two_hours_ago_utc = now_utc - datetime.timedelta(hours=2)
        handled_demarches = []

        logging.info(
            f"Get « Démarche numérique » files updated since {two_hours_ago_utc}"
        )

        # As long as a demarche number is set, we run the sync
        # (even if the dept is not activated yet)
        configs_with_ds = (
            ConfigHaie.objects.filter(demarche_numerique_config__isnull=False)
            .select_related("demarche_numerique_config")
            .valid_at(timezone.now().date())
        )
        for config in configs_with_ds:
            demarche_number = config.demarche_numerique_config.demarche_numerique_number
            project_url_id = config.demarche_numerique_config.display_fields.get(
                "project_url", None
            )
            if not project_url_id:
                # A DN config should always have "project_url" in display_fields
                continue

            logging.info(f"Handling demarche {demarche_number} ({config})")

            if demarche_number in handled_demarches:
                continue

            try:
                self.synchronize_demarche(
                    demarche_number, project_url_id, two_hours_ago_utc
                )
            except DemarcheNumeriqueError:
                # The client has already alerted the team.
                logger.warning(
                    "Could not fetch the dossiers of a « Démarche numérique » démarche",
                    extra={"demarche_number": demarche_number},
                )
            handled_demarches.append(demarche_number)

    def synchronize_demarche(self, demarche_number, project_url_id, updated_since):
        """Sync the démarche's dossiers updated since `updated_since`."""
        ds_client = DemarcheNumeriqueClient()
        demarche = ds_client.get_dossiers_for_demarche(demarche_number, updated_since)
        if not demarche:
            return

        for dossier_as_dict in demarche.dossiers:
            try:
                self.handle_dossier(dossier_as_dict, demarche, project_url_id)
            # Any failure: one dossier must not cost the others their sync.
            except Exception:
                logger.exception(
                    "Could not sync a « Démarche numérique » dossier",
                    extra={"dossier_number": dossier_as_dict.get("number")},
                )

    def handle_dossier(self, dossier_as_dict, demarche, project_url_id):
        """Sync the dossier's project, or report the dossier when no project matches."""
        dossier = Dossier.from_dict(dossier_as_dict)
        project = (
            PetitionProject.objects.filter(
                demarche_numerique_dossier_number=dossier.number
            )
            .prefetch_related("simulations")
            .first()
        )
        if project is None:
            self.handle_unlinked_dossier(dossier, demarche, project_url_id)
        else:
            project.synchronize_with_demarche_numerique(dossier_as_dict)

    def handle_unlinked_dossier(self, dossier, demarche, project_url_id):
        """Handle a dossier that is not linked to any project in the database

        This dossier is not linked to any project on this environment
        it may have been created on another environment
        or it may have been created from scratch without the guh
        or it may be a duplicate of a GUH created dossier
        we will try to find out and apply a notification strategy
        """
        project_url = next(
            (
                champ.stringValue
                for champ in dossier.champs
                if champ.id == project_url_id
            ),
            "",
        )

        demarche_name = demarche.title if demarche is not None else "Nom inconnu"
        demarche_number = demarche.number if demarche is not None else "Numéro inconnu"
        ds_url = (
            f"{settings.DEMARCHE_NUMERIQUE["DOSSIER_BASE_URL"]}/procedures/{demarche_number}/"
            f"dossiers/{dossier.number}/"
        )

        if any(domain in project_url for domain in DOMAIN_BLACK_LIST):
            # project url is from a blacklisted domain, it should have been created in another environment
            logger.warning(
                "A « Démarche numérique » dossier has no corresponding project, it was probably "
                "created on another environment",
                extra={
                    "dossier_number": dossier.number,
                    "demarche_number": demarche_number,
                    "project_url": project_url,
                },
            )
        else:
            # Either this dossier has been created in this environment but do not match an existing project,
            # or it has been created in a heterodox way.
            logger.warning(
                "A « Démarche numérique » dossier has no corresponding project, it may have been "
                "created without the guh",
                extra={
                    "dossier_number": dossier.number,
                    "demarche_number": demarche_number,
                    "project_url": project_url,
                },
            )
            message_body = render_to_string(
                "haie/petitions/mattermost_unlinked_dossier_notif.txt",
                context={
                    "demarche_name": demarche_name,
                    "ds_url": ds_url,
                    "dossier_number": dossier.number,
                },
            )
            notify(message_body, "haie")
