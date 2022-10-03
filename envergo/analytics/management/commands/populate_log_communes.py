from django.core.management.base import BaseCommand

from envergo.analytics.models import Event
from envergo.geodata.utils import get_commune_from_coords


class Command(BaseCommand):
    help = "Populate geographical fields for log events"

    def handle(self, *args, **options):

        events = Event.objects.filter(
            metadata__lat__isnull=False, metadata__lng__isnull=False
        ).exclude(metadata__has_key="commune")
        for event in events:
            commune = get_commune_from_coords(
                event.metadata["lng"], event.metadata["lat"]
            )
            event.metadata["commune"] = commune or ""
            event.save()

            print(f'{event.metadata["lng"]},{event.metadata["lat"]}, {commune}')

        self.stdout.write(self.style.SUCCESS("Updated some event records"))
