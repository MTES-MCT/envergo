import datetime
import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from envergo.analytics.models import Event
from envergo.moulinette.models import ConfigHaie
from envergo.petitions.demarches_simplifiees.client import DemarchesSimplifieesClient
from envergo.petitions.models import PetitionProject
from envergo.utils.mattermost import notify

logger = logging.getLogger(__name__)

# This session key is used when we are not able to find the real user session key.
SESSION_KEY = "untracked_dossier_submission"

DOMAIN_BLACK_LIST = settings.DEMARCHES_SIMPLIFIEES["DOSSIER_DOMAIN_BLACK_LIST"]


class Command(BaseCommand):
    help = "Fetch freshly submitted dossier on Démarches Simplifiées and notify admins."

    def handle(self, *args, **options):
        """get all the dossier updated in the last hour"""

        if not settings.DEMARCHES_SIMPLIFIEES["ENABLED"]:
            logger.warning("Demarches Simplifiees is not enabled. Doing nothing.")
            return None

        now_utc = datetime.datetime.now(datetime.UTC)
        # NB: if you change this timedelta, you should also change the cron job frequency
        # The cron job is run every hour.
        # We fetch the updates from the last 2 hours to be sure as we may have some delay in the cron job execution
        two_hours_ago_utc = now_utc - datetime.timedelta(hours=2)

        current_site = Site.objects.get(domain=settings.ENVERGO_HAIE_DOMAIN)
        handled_demarches = []

        for activated_department in ConfigHaie.objects.filter(
            is_activated=True, demarche_simplifiee_number__isnull=False
        ).all():
            demarche_number = activated_department.demarche_simplifiee_number
            if demarche_number in handled_demarches:
                continue

            ds_client = DemarchesSimplifieesClient()

            demarche = ds_client.get_dossiers_for_demarche(
                demarche_number, two_hours_ago_utc
            )

            if not demarche:
                continue

            demarche_name = demarche.title or "Nom inconnu"
            demarche_label = f"la démarche n°{demarche_number} ({demarche_name})"
            for dossier in demarche.dossiers:
                dossier_number = dossier.number
                project = PetitionProject.objects.filter(
                    demarches_simplifiees_dossier_number=dossier_number
                ).first()

                ds_url = (
                    f"https://www.demarches-simplifiees.fr/procedures/{demarche_number}/dossiers/"
                    f"{dossier_number}"
                )
                if project is None:
                    self.handle_unlinked_dossier(
                        dossier,
                        demarche_number,
                        demarche_name,
                        ds_url,
                        activated_department.demarches_simplifiees_project_url_id,
                    )
                    continue

                creation_event = (
                    Event.objects.order_by("-date_created")
                    .filter(
                        metadata__reference=project.reference,
                        category="dossier",
                        event="creation",
                    )
                    .first()
                )
                if not creation_event:
                    logger.warning(
                        f"Unable to find creation event for project {project.reference}. "
                        f"The submission event will be logged with a mocked session key.",
                        extra={
                            "project": self,
                            "session_key": SESSION_KEY,
                        },
                    )

                visitor_id = (
                    creation_event.session_key if creation_event else SESSION_KEY
                )
                user = type("User", (object,), {"is_staff": False})()
                project.synchronize_with_demarches_simplifiees(
                    dossier, current_site, demarche_label, ds_url, visitor_id, user
                )

            handled_demarches.append(demarche_number)

    def handle_unlinked_dossier(
        self, dossier, demarche_number, demarche_name, ds_url, project_url_id
    ):
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
