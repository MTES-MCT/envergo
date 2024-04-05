from django.conf import settings
from django.core.management.base import BaseCommand

from envergo.evaluations.models import Request


class Command(BaseCommand):
    help = "Delete all test requests and their associated files"

    def handle(self, *args, **options):
        test_evalreqs = Request.objects.filter(
            contact_emails__contains=[settings.TEST_EMAIL]
        )
        self.stdout.write(f"Deleting {test_evalreqs.count()} test requests")

        for evalreq in test_evalreqs:
            for file in evalreq.additional_files.all():
                file.file.delete()
                file.delete()
            evalreq.delete()
