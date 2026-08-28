import csv
import logging
import shutil
from os.path import splitext
from tempfile import NamedTemporaryFile

from django.contrib.gis.gdal import DataSource
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from config.celery_app import app
from envergo.geodata.import_batch import is_blank_row, parse_batch_row, validate_headers
from envergo.geodata.models import STATUSES, Map, MapImportBatch
from envergo.geodata.utils import (
    count_features,
    extract_map,
    make_polygons_valid,
    process_lines_file,
    process_zones_file,
    read_csv_file,
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


# `autoretry_for=()` opts out of the BaseTaskWithRetry policy: a retry
# would re-queue `process_map` for maps already handled in a previous run.
@app.task(bind=True, autoretry_for=())
def process_map_import_batch(task, batch_id):
    """Create or update Map objects described in a batch CSV.

    Each CSV row is processed in isolation inside its own transaction:
    a failing row is logged and never prevents the other rows from being
    imported. The geometry extraction itself is delegated to the existing
    `process_map` task, one per map, once the batch is fully processed.
    """
    logger.info(f"Starting import on map batch {batch_id}")

    batch = MapImportBatch.objects.get(pk=batch_id)

    # Store the task data in the model, so we can display progression
    # in the admin page.
    batch.task_id = task.request.id
    batch.import_log = ""
    batch.import_status = None
    batch.save()

    import_log = []
    maps_to_process = []

    reader = csv.DictReader(read_csv_file(batch.csv_file))

    # A missing required column is batch-fatal: no row can be processed
    # reliably, so no Map is touched.
    header_errors = validate_headers(reader.fieldnames)
    if header_errors:
        batch.import_status = STATUSES.failure
        batch.import_log = "\n".join(header_errors)
        batch.import_date = timezone.now()
        batch.task_id = None
        batch.save()
        return

    files_by_name = {f.name: f for f in batch.files.all()}
    seen_references = set()

    rows = [row for row in reader if not is_blank_row(row)]
    nb_rows = len(rows)
    nb_ok = 0

    # Header is line 1, so the first data row is line 2.
    for line_no, raw_row in enumerate(rows, start=2):
        result, errors = parse_batch_row(line_no, raw_row)
        if errors:
            import_log.extend(errors)
            continue

        if result.reference in seen_references:
            import_log.append(
                f"ligne {line_no} : référence {result.reference} en double, "
                f"ligne ignorée"
            )
            continue
        seen_references.add(result.reference)

        batch_file = None
        if result.file:
            batch_file = files_by_name.get(result.file)
            if batch_file is None:
                import_log.append(
                    f"ligne {line_no} : fichier {result.file} absent des "
                    f"fichiers téléversés"
                )
                continue

        try:
            with transaction.atomic():
                map = import_batch_row(result, batch, batch_file)
            if batch_file is not None:
                maps_to_process.append(map.pk)
            nb_ok += 1
        except Exception as e:
            message = f"ligne {line_no} ({result.reference}) : {e}"
            import_log.append(message)
            logger.error(message)

        task.update_state(
            state="PROGRESS",
            meta={"msg": f"{line_no - 1}/{nb_rows} lignes traitées"},
        )

    if nb_ok == nb_rows:
        batch.import_status = STATUSES.success
    elif nb_ok > 0:
        batch.import_status = STATUSES.partial_success
    else:
        batch.import_status = STATUSES.failure

    batch.import_log = "\n".join(import_log)
    batch.import_date = timezone.now()
    batch.task_id = None
    batch.save()

    # Queue the geometry imports only once the batch bookkeeping is
    # written, so an operator always sees a consistent batch status.
    for map_id in maps_to_process:
        process_map.delay(map_id)


def import_batch_row(row, batch, batch_file):
    """Create or update the Map described by a parsed CSV row.

    Required columns always overwrite; optional columns only when
    non-empty. Blank required cells are rejected upstream by
    `parse_batch_row`, except `departments`, where a blank cell means
    "aucun département" and clears the field.

    `batch_file` is None for a metadata-only update (blank file cell): the
    map's file and `expected_geometries` are left untouched and its geometry
    is never re-imported. Such a row can only target an existing map. When a
    file is provided, it is copied from the upload bucket to the default
    (media) storage, where every existing map tool expects it.
    """
    now = timezone.now()

    map = Map.objects.filter(reference=row.reference).first()
    if map is None:
        if batch_file is None:
            raise ValueError("carte inexistante : un fichier est requis pour la créer")
        map = Map(reference=row.reference, batch_created_at=now)

    map.name = row.name
    map.description = row.description
    map.departments = row.departments or None
    if row.display_name:
        map.display_name = row.display_name
    if row.source:
        map.source = row.source
    if row.map_type:
        map.map_type = row.map_type
    if row.data_type:
        map.data_type = row.data_type
    if row.display_for_user is not None:
        map.display_for_user = row.display_for_user

    map.import_batch = batch
    map.batch_updated_at = now

    if batch_file is not None:
        _, extension = splitext(row.file)
        with NamedTemporaryFile(suffix=extension) as tmp:
            with batch_file.file.open("rb") as source:
                shutil.copyfileobj(source, tmp)
            tmp.seek(0)

            map_file = File(tmp)
            map.expected_geometries = count_features(map_file)
            map.file.save(row.file, map_file, save=False)

    map.save()
    return map


@app.task(bind=True)
def generate_map_preview(task, map_id):
    logger.info(f"Starting preview generation on map {map_id}")

    map = Map.objects.get(pk=map_id)
    if map.zones.count() > 0:
        map.geometry = simplify_map(map)
    elif map.lines.count() > 0:
        map.geometry = simplify_lines(map)

    map.save()
