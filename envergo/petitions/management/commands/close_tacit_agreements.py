import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import set_urlconf
from django.utils import timezone

from envergo.petitions.models import PetitionProject

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Close the dossiers whose silence became agreement, with their attestation."

    def handle(self, *args, **options):
        """Close every dossier due for a tacit agreement today."""
        if not settings.DEMARCHE_NUMERIQUE["ENABLED"]:
            logger.warning("« Démarche numérique » is not enabled. Doing nothing.")
            return

        # The URL configuration is set per thread and outlives the command.
        set_urlconf("config.urls_haie")
        try:
            self.close_due_dossiers()
        finally:
            set_urlconf(None)

    def close_due_dossiers(self):
        """Close each due dossier. A dossier that fails stays due for the next run."""
        today = timezone.localdate()
        due_projects = PetitionProject.objects.due_for_tacit_agreement(today)

        closed_count = 0
        failed_count = 0
        for project in due_projects:
            try:
                project.close_by_tacit_agreement()
            except Exception:
                # One broken dossier must not block the others.
                logger.exception(
                    "Tacit agreement closing failed for dossier %s", project.reference
                )
                failed_count += 1
            else:
                closed_count += 1

        logger.info(
            "Tacit agreements: %d dossiers closed, %d failed.",
            closed_count,
            failed_count,
        )
