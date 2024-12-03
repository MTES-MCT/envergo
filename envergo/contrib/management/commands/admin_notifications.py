import logging

from django.core.management import BaseCommand

from envergo.evaluations.management.commands import new_files_admin_alert
from envergo.petitions.management.commands import dossier_submission_admin_alert

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run different notification command for admins."

    def handle(self, *args, **options):
        try:
            new_files_admin_alert.Command().handle()
        except Exception as e:
            logger.error("new_files_admin_alert failed: %s", e)

        try:
            dossier_submission_admin_alert.Command().handle()
        except Exception as e:
            logger.error("dossier_submission_admin_alert failed: %s", e)
