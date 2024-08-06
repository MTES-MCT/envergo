from django.contrib.sites.models import Site
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set the url of the EnvErgo Amenagement Site on the new environment."

    def add_arguments(self, parser):
        parser.add_argument(
            "url",
            help="The url of the new environment.",
        )

    def handle(self, *args, **options):
        if "url" not in options:
            raise CommandError("The environment url is required.")

        Site.objects.first().update(
            domain=options["url"]
        )  # the first one should be EnvErgo Amenagement

        self.stdout.write(
            self.style.SUCCESS("Successfully updated the environment url.")
        )
