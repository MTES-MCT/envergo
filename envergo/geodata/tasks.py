import logging
import sys

from django.db import transaction

from config.celery_app import app
from envergo.geodata.models import Map
from envergo.geodata.utils import extract_shapefile

logger = logging.getLogger(__name__)


class CeleryDebugStream:
    def __init__(self, task):
        self.task = task

    def write(self, msg):
        logger.info(f"Writing debug message to task state {msg}")
        self.task.update_state(state="PROGRESS", meta={"msg": msg})
        sys.stdout.write(msg)


@app.task(bind=True)
def process_shapefile_map(task, map_id):
    """Send a Mattermost notification to confirm the evaluation request."""

    logger.info(f"Starting import on map {map_id}")
    map = Map.objects.get(pk=map_id)
    debug_stream = CeleryDebugStream(task)

    task.update_state(state="PROGRESS", meta={"debug": "debug message"})

    with transaction.atomic():
        map.zones.all().delete()
        extract_shapefile(map, map.file, debug_stream)
