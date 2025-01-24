import logging

from django.db import transaction
from django.utils import timezone

from config.celery_app import app
from envergo.geodata.models import STATUSES, Map
from envergo.geodata.utils import make_polygons_valid, process_map_file, simplify_map

logger = logging.getLogger(__name__)


@app.task(bind=True)
@transaction.atomic
def process_map(task, map_id):
    logger.info(f"Starting import on map {map_id}")

    map = Map.objects.get(pk=map_id)

    # Store the task data in the model, so we can display progression
    # in the admin page.
    map.task_id = task.request.id
    map.import_error_msg = ""
    map.import_status = None
    map.save()

    # Proceed with the map import
    try:
        with transaction.atomic():
            map.zones.all().delete()
            process_map_file(map, map.file, task)
            make_polygons_valid(map)
            map.geometry = simplify_map(map)
    except Exception as e:
        map.import_error_msg = f"Erreur d'import ({e})"
        logger.error(map.import_error_msg)

    # Update the map status and metadata
    nb_imported_zones = map.zones.all().count()
    if map.expected_zones == nb_imported_zones:
        map.import_status = STATUSES.success
    elif nb_imported_zones > 0:
        map.import_status = STATUSES.partial_success
    else:
        map.import_status = STATUSES.failure

    map.task_id = None
    map.imported_zones = nb_imported_zones
    map.import_date = timezone.now()
    map.save()


@app.task(bind=True)
def generate_map_preview(task, map_id):
    logger.info(f"Starting preview generation on map {map_id}")

    map = Map.objects.get(pk=map_id)
    map.geometry = simplify_map(map)
    map.save()
