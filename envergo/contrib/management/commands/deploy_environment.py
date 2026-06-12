from django.contrib.sites.models import Site
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Set the url of the Envergo Amenagement Site on the new environment if it is not already set (either on GUH"
        " or Envergo Amenagement)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "url",
            help="The url of the new environment.",
        )

    def handle(self, *args, **options):
        if "url" not in options:
            raise CommandError("The environment url is required.")
        if Site.objects.filter(domain=options["url"]).exists():
            return
        site = Site.objects.order_by(
            "id"
        ).first()  # the first one should be Envergo Amenagement
        site.domain = options["url"]
        site.save()

        self.stdout.write(
            self.style.SUCCESS("Successfully updated the environment url.")
        )
