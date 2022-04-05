import logging

from django.db import transaction

from config.celery_app import app
from envergo.geodata.models import Map
from envergo.geodata.utils import process_shapefile

logger = logging.getLogger(__name__)


@app.task(bind=True)
def process_shapefile_map(task, map_id):
    logger.info(f"Starting import on map {map_id}")

    map = Map.objects.get(pk=map_id)
    map.task_id = task.request.id
    map.import_error_msg = ""
    map.save()

    map.zones.all().delete()
    try:
        with transaction.atomic():
            process_shapefile(map, map.file, task)
    except Exception as e:
        map.import_error_msg = f"Erreur d'import ({e})"

    map.task_id = None
    map.save()
