from django.core.management import BaseCommand

from envergo.contrib.tasks import execute_s3_backup


class Command(BaseCommand):
    help = "backup all the files in the s3 bucket to a cold storage."

    def handle(self, *args, **options):
        execute_s3_backup()
