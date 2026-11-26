import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import set_urlconf
from django.utils import timezone

from envergo.petitions.models import PetitionProject

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Close the dossiers whose silence became agreement, with their attestation."

    def add_arguments(self, parser):
        """Declare the command's options."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the due dossiers without closing them.",
        )

    def handle(self, *args, **options):
        """Close every dossier due for a tacit agreement today."""
        if not settings.DEMARCHE_NUMERIQUE["ENABLED"]:
            logger.warning("« Démarche numérique » is not enabled. Doing nothing.")
            return

        today = timezone.localdate()
        due_projects = PetitionProject.objects.due_for_tacit_agreement(today)

        if options["dry_run"]:
            self.list_due_dossiers(due_projects)
        else:
            # The URL configuration is set per thread and outlives the command.
            set_urlconf("config.urls_haie")
            try:
                self.close_due_dossiers(due_projects)
            finally:
                set_urlconf(None)

    def list_due_dossiers(self, due_projects):
        """Log each due dossier with its deadline, and change nothing."""
        for project in due_projects:
            logger.info(
                "Dry run: dossier %s is due since %s.",
                project.reference,
                project.silence_deadline,
            )

        logger.info("Dry run: %d dossiers would be closed.", len(due_projects))

    def close_due_dossiers(self, due_projects):
        """Close each due dossier. A dossier that fails stays due for the next run."""
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
