import logging

from django.contrib.gis.gdal import DataSource
from django.db import transaction
from django.utils import timezone

from config.celery_app import app
from envergo.geodata.models import STATUSES, Map
from envergo.geodata.utils import (
    extract_map,
    make_polygons_valid,
    process_lines_file,
    process_zones_file,
    simplify_lines,
    simplify_map,
)

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
            map.lines.all().delete()

            logger.info("Creating temporary directory")
            with extract_map(map.file) as map_file:
                ds = DataSource(map_file)
                layer = ds[0]
                geom_type = layer.geom_type.name
                if geom_type in ("LineString", "MultiLineString"):
                    process_lines_file(map, map_file, task)
                    map.geometry = simplify_lines(map)
                else:
                    process_zones_file(map, map_file, task)
                    make_polygons_valid(map)
                    map.geometry = simplify_map(map)

    except Exception as e:
        map.import_error_msg = f"Erreur d'import ({e})"
        logger.error(map.import_error_msg)

    # Update the map status and metadata
    nb_imported_geometries = max(map.zones.all().count(), map.lines.all().count())
    if map.expected_geometries == nb_imported_geometries:
        map.import_status = STATUSES.success
    elif nb_imported_geometries > 0:
        map.import_status = STATUSES.partial_success
    else:
        map.import_status = STATUSES.failure

    map.task_id = None
    map.imported_geometries = nb_imported_geometries
    map.import_date = timezone.now()
    map.save()


@app.task(bind=True)
def generate_map_preview(task, map_id):
    logger.info(f"Starting preview generation on map {map_id}")

    map = Map.objects.get(pk=map_id)
    if map.zones.count() > 0:
        map.geometry = simplify_map(map)
    elif map.lines.count() > 0:
        map.geometry = simplify_lines(map)

    map.save()
