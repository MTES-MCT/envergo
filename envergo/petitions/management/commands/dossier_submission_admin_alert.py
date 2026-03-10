import datetime
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import set_urlconf
from django.utils import timezone

from envergo.moulinette.models import ConfigHaie
from envergo.petitions.demarches_simplifiees.client import DemarchesSimplifieesClient
from envergo.petitions.demarches_simplifiees.models import Dossier
from envergo.petitions.models import PetitionProject
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)

DOMAIN_BLACK_LIST = settings.DEMARCHES_SIMPLIFIEES["DOSSIER_DOMAIN_BLACK_LIST"]


class Command(BaseCommand):
    help = "Fetch freshly submitted dossier on Démarches Simplifiées and notify admins."

    def handle(self, *args, **options):
        """get all the dossier updated in the last hour"""

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning("Demarches Simplifiees is not enabled. Doing nothing.")
            return None
        set_urlconf("config.urls_haie")

        now_utc = datetime.datetime.now(datetime.UTC)
        # NB: if you change this timedelta, you should also change the cron job frequency
        # The cron job is run every hour.
        # We fetch the updates from the last 2 hours to be sure as we may have some delay in the cron job execution
        two_hours_ago_utc = now_utc - datetime.timedelta(hours=2)
        handled_demarches = []

        logging.info(f"Get DS files updated since {two_hours_ago_utc}")

        # As long as a demarche number is set, we run the sync
        # (even if the dept is not activated yet)
        configs_with_ds = ConfigHaie.objects.filter(
            demarche_simplifiee_number__isnull=False
        ).valid_at(timezone.now().date())
        for config in configs_with_ds:
            demarche_number = config.demarche_simplifiee_number

            logging.info(f"Handling demarche {demarche_number} ({config})")

            if demarche_number in handled_demarches:
                continue

            ds_client = DemarchesSimplifieesClient()

            demarche = ds_client.get_dossiers_for_demarche(
                demarche_number, two_hours_ago_utc
            )

            if not demarche:
                continue

            for dossier_as_dict in demarche.dossiers:
                dossier = Dossier.from_dict(dossier_as_dict)
                dossier_number = dossier.number
                project = PetitionProject.objects.filter(
                    demarches_simplifiees_dossier_number=dossier_number
                ).first()
                if project is None:
                    self.handle_unlinked_dossier(
                        dossier,
                        demarche,
                        config,
                    )
                    continue

                project.synchronize_with_demarches_simplifiees(dossier_as_dict)

            handled_demarches.append(demarche_number)

        set_urlconf(None)

    def handle_unlinked_dossier(self, dossier, demarche, config):
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
                if champ.id == config.demarches_simplifiees_project_url_id
            ),
            "",
        )

        demarche_name = demarche.title if demarche is not None else "Nom inconnu"
        demarche_number = demarche.number if demarche is not None else "Numéro inconnu"
        ds_url = (
            f"{settings.DEMARCHES_SIMPLIFIEES["DOSSIER_BASE_URL"]}/procedures/{demarche_number}/"
            f"dossiers/{dossier.number}/"
        )

        if any(domain in project_url for domain in DOMAIN_BLACK_LIST):
            # project url is from a blacklisted domain, it should have been created in another environment
            logger.warning(
                "A demarches simplifiees dossier has no corresponding project, it was probably "
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
                "A demarches simplifiees dossier has no corresponding project, it may have been "
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
