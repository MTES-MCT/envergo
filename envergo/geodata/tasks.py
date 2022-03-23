import logging

from celery.exceptions import Ignore
from django.db import transaction

from config.celery_app import app
from envergo.geodata.models import Map
from envergo.geodata.utils import extract_shapefile

logger = logging.getLogger(__name__)


@app.task(bind=True)
def process_shapefile_map(task, map_id):
    """Send a Mattermost notification to confirm the evaluation request."""

    logger.info(f"Starting import on map {map_id}")

    map = Map.objects.get(pk=map_id)
    map.task_id = task.request.id
    map.save()

    map.zones.all().delete()

    with transaction.atomic():
        try:
            extract_shapefile(map, map.file, task)
        except Exception as e:
            task.update_state("FAILURE", meta={"msg": f"Erreur d'import ({e})"})
            # We have to raise the `Ignore` exception, otherwise celery
            # will change end the task with a SUCCESS status.
            raise Ignore()

    map.task_id = None
    map.save()
