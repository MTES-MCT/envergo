from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import localtime

from envergo.evaluations.models import Request


class Command(BaseCommand):
    help = "Delete all test and invalid requests and their associated files"

    def handle(self, *args, **options):
        test_evalreqs = Request.objects.filter(
            contact_emails__contains=[settings.TEST_EMAIL]
        )
        one_hr_ago = localtime() - timedelta(hours=1)
        unsubmitted_evalreqs = Request.objects.filter(
            created_at__lte=one_hr_ago, submitted=False
        )

        self.stdout.write(
            f"Deleting {test_evalreqs.count()} test requests / {unsubmitted_evalreqs.count()} unsubmitted requests"
        )

        for evalreq in list(test_evalreqs) + list(unsubmitted_evalreqs):
            for file in evalreq.additional_files.all():
                file.file.delete()
                file.delete()
            evalreq.delete()
