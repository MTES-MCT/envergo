from django.core.management import BaseCommand

from envergo.contrib.tasks import execute_s3_backup


class Command(BaseCommand):
    help = "backup all the files in the s3 bucket to a cold storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "scaleway_access_key",
            help="Scaleway S3 access key.",
        )
        parser.add_argument(
            "scaleway_secret_key",
            help="Scaleway S3 secret key.",
        )

    def handle(self, *args, **options):
        execute_s3_backup.delay(
            options["scaleway_access_key"], options["scaleway_secret_key"]
        )
