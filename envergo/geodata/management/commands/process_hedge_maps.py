from logging import getLogger

from django.core.management.base import BaseCommand

from envergo.geodata.models import Map
from envergo.geodata.tasks import process_map

logger = getLogger(__name__)


class Command(BaseCommand):
    help = """Trigger the import of all hedges maps.

    This is meant to be used after the "batch_process_map" has been run.
    """

    def handle(self, *args, **options):
        qs = Map.objects.filter(import_status__isnull=True)
        for map in qs:
            process_map.delay(map.id)
