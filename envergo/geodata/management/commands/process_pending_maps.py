"""Schedule async processing for every Map that hasn't been processed yet.

Use after `batch_import_maps` to fire the Celery jobs that turn the uploaded
files into Zone or Line rows. The actual processing is done by
`envergo.geodata.tasks.process_map`, which branches on the file's geometry
type and DELETES any pre-existing zones/lines for the map before re-importing.

Because the queued task is destructive on the database the Celery worker
talks to, this command refuses to run from a production-flavoured settings
module and always asks for interactive confirmation, displaying the target
database before scheduling anything.
"""

import sys
from logging import getLogger

from django.core.management.base import BaseCommand

from envergo.geodata.management.helpers import (
    VALID_MAP_TYPES,
    get_default_db_identity,
    refuse_production_settings,
)
from envergo.geodata.models import Map
from envergo.geodata.tasks import process_map

logger = getLogger(__name__)


class Command(BaseCommand):
    help = """Trigger asynchronous processing of every Map that hasn't been
    processed yet (import_status IS NULL). Each scheduled task will DELETE
    the existing zones/lines for the map before re-importing — see the
    module docstring for the safety contract.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--map-type",
            choices=sorted(VALID_MAP_TYPES),
            help="Restrict to maps of this type",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Process at most this many maps (useful for staged rollouts)",
        )

    def handle(self, *args, **options):
        """Schedule async processing for every Map that hasn't been processed.

        Refuses to run with a production-flavoured settings module before
        querying anything. Always asks for an interactive confirmation
        showing the destination database, since each scheduled task
        deletes existing zones/lines for its map before re-importing.
        """
        refuse_production_settings()

        qs = Map.objects.filter(import_status__isnull=True)
        if options["map_type"]:
            qs = qs.filter(map_type=options["map_type"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        # Materialise once: COUNT and iteration could disagree.
        maps = list(qs)
        if not maps:
            self.stdout.write("No pending maps to process.")
            return

        self.stdout.write(
            self.style.WARNING(
                f"About to schedule processing for {len(maps)} maps in "
                f"{get_default_db_identity()}.\n"
                f"Each scheduled job will DELETE the existing zones/lines "
                f"for its map before re-importing."
            )
        )
        confirm = input("Type 'yes' to continue: ").strip()
        if confirm != "yes":
            self.stdout.write("Operation cancelled.")
            sys.exit(0)

        for map_obj in maps:
            process_map.delay(map_obj.id)
            self.stdout.write(f"  - queued map {map_obj.id} ({map_obj.name})")
