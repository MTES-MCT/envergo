from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set the url of the EnvErgo tool on the new environment."

    def add_arguments(self, parser):
        parser.add_argument("url", nargs=1, type=str)

    def handle(self, *args, **options):
        if "url" not in options:
            raise CommandError("The environment url is required.")

        Site.objects.filter(id=settings.SITE_ID).update(domain=options["url"])

        self.stdout.write(
            self.style.SUCCESS("Successfully updated the environment url.")
        )
