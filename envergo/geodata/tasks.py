import csv
import logging

from celery import chain
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from config.celery_app import BaseTaskWithRetry, app
from envergo.geodata.import_batch import is_blank_row, is_file_valid, is_line_valid
from envergo.geodata.models import STATUSES, Map, MapImportBatch
from envergo.geodata.utils import (
    make_polygons_valid,
    open_map_file,
    process_lines_file,
    process_zones_file,
    read_csv_file,
    simplify_lines,
    simplify_map,
)

logger = logging.getLogger(__name__)


class ProcessMapTask(BaseTaskWithRetry):
    """Make sure a map never stays silently unprocessed."""

    max_retries = 1

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        # The task is waiting for its next attempt, not stalled: restart the
        # stalled import delay.
        Map.objects.filter(pk=args[0] if args else kwargs.get("map_id")).update(
            import_date=timezone.now()
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        map_id = args[0] if args else kwargs.get("map_id")
        Map.objects.filter(pk=map_id).update(
            import_status=STATUSES.failure,
            import_error_msg=f"Erreur d'import ({exc})",
            import_date=timezone.now(),
            task_id=None,
        )


@app.task(bind=True, base=ProcessMapTask)
def process_map(task, map_id):
    logger.info(f"Starting import on map {map_id}")
    map = Map.objects.get(pk=map_id)

    # Store the task data in the model, so we can display progression
    # in the admin page.
    map.task_id = task.request.id
    map.import_error_msg = ""
    map.import_status = None
    map.import_date = timezone.now()
    map.save()

    # Proceed with the map import
    with transaction.atomic():
        map.zones.all().delete()
        map.lines.all().delete()

        # open_map_file leaves the stored file open. Close it once imported.
        with map.file.open("rb"), open_map_file(map.file) as data_source:
            geom_type = data_source[0].geom_type.name
            if geom_type in ("LineString", "MultiLineString"):
                process_lines_file(map, data_source, task)
                map.geometry = simplify_lines(map)
            else:
                process_zones_file(map, data_source, task)
                make_polygons_valid(map)
                map.geometry = simplify_map(map)

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


def process_maps(map_ids):
    """Queue the geometry import of several maps, one after the other.

    Chaining the process avoid a too heavy load on DB and memory for big objects
    """
    if map_ids:
        chain(*(process_map.si(map_id) for map_id in map_ids)).delay()


@app.task(max_retries=0)
def process_map_import_batch(batch_id):
    """Create or update Map objects described in a batch CSV.

    The CSV is validated first: any error fails the batch before any import.
    Rows are then imported one at a time in a sequential chain.
    A row that fails validation again is logged and skipped.
    Any other error, timeouts included, stops the chain and mark the batch as failed.
    """
    logger.info(f"Starting import on map batch {batch_id}")

    batch = MapImportBatch.objects.get(pk=batch_id)

    # Reset the state of a previous run.
    batch.import_log = ""
    batch.import_status = None
    batch.save()

    errors = is_file_valid(batch.csv_file, batch.files)

    if errors:
        batch.import_status = STATUSES.failure
        batch.import_log = "\n".join(
            ["Résumé : aucune ligne importée, csv non valide.", *errors]
        )
        batch.import_date = timezone.now()
        batch.save()
        return

    reader = csv.DictReader(read_csv_file(batch.csv_file))
    rows = [(reader.line_num, row) for row in reader if not is_blank_row(row)]
    nb_rows = len(rows)

    if nb_rows == 0:
        batch.import_status = STATUSES.success
        batch.import_date = timezone.now()
        batch.save()
        return

    chain(
        # Each task receives the previous one's `errors_by_line`; the first
        # one has no predecessor, so it gets None explicitly.
        import_batch_row.s(None, batch_id, 0, nb_rows, *rows[0]),
        *(
            import_batch_row.s(batch_id, index, nb_rows, csv_line_number, raw_row)
            for index, (csv_line_number, raw_row) in enumerate(rows)
            if index > 0
        ),
        finalize_batch.s(batch_id, nb_rows),
    ).apply_async(link_error=fail_batch.s(batch_id, nb_rows))


def append_batch_log(batch, line):
    """Add a line to the batch log, so the progress survives a broken chain.

    Rows are processed one at a time, so there is no concurrent write.
    """
    batch.import_log = "\n".join(filter(None, [batch.import_log, line]))
    batch.save(update_fields=["import_log"])


@app.task
def fail_batch(request, exc, traceback, batch_id, total):
    """Error callback of the batch chain: record the failure on the batch."""
    batch = MapImportBatch.objects.get(pk=batch_id)
    if batch.import_status == STATUSES.failure:
        # The callback is linked to every task of the chain: only the first
        # call describes the failure, later ones must not rewrite the log.
        return

    logged = batch.import_log.splitlines()
    position = len(logged) + 1

    if position > total:
        # Every row was handled: only the finalization failed.
        summary = f"Résumé : import interrompu à la finalisation ({exc})."
        lines = logged
    else:
        summary = (
            f"Résumé : import interrompu à la ligne {position}/{total} "
            f"par une erreur inattendue, {total - position} ligne(s) non traitée(s)."
        )
        lines = [
            *logged,
            f"L'import {position}/{total} a échoué : erreur inattendue ({exc})",
        ]
    batch.import_status = STATUSES.failure
    batch.import_log = "\n".join([summary, *lines])
    batch.import_date = timezone.now()
    batch.save()


@app.task
def finalize_batch(errors_by_line, batch_id, total):
    """Write the batch outcome on top of the per-row lines of the log."""
    batch = MapImportBatch.objects.get(pk=batch_id)
    nb_failed = len(errors_by_line or {})
    if nb_failed == 0:
        batch.import_status = STATUSES.success
    elif nb_failed < total:
        batch.import_status = STATUSES.partial_success
    else:
        batch.import_status = STATUSES.failure

    summary = f"Résumé : {total - nb_failed}/{total} ligne(s) importée(s)."
    batch.import_log = "\n".join(filter(None, [summary, batch.import_log]))
    batch.import_date = timezone.now()
    batch.save()


@app.task(bind=True)
def import_batch_row(
    task, errors_by_line, batch_id, index, total, csv_line_number, raw_row
):
    """Create or update the Map described by a CSV row, and then process it if needed.

    Chained task: it receives the `errors_by_line` dict ({row index: [errors]})
    from the previous row and returns it, completed, to the next one.

    Each row logs its outcome on the batch as it goes. A row failing
    validation is added to `errors_by_line` and skipped.
    Otherwise the map is saved: required columns always overwrite, optional
    ones only when non-empty, and a blank `departments` clears the field.
    A row with a file replaces the map's file; a blank file cell only updates
    the metadata of an existing map. The task then replaces itself with
    `process_map`, so the next row starts once the geometries are imported.
    """
    if errors_by_line is None:
        errors_by_line = {}
    batch = MapImportBatch.objects.get(pk=batch_id)
    row, errors = is_line_valid(csv_line_number, raw_row, batch.files)
    if errors:
        errors_by_line[index] = errors
        append_batch_log(
            batch, f"L'import {index + 1}/{total} a échoué : {' ; '.join(errors)}"
        )
        return errors_by_line

    now = timezone.now()

    map = Map.objects.filter(reference=row.reference).first()
    batch_file = batch.files.filter(name=row.file).first()
    if map is None:
        if batch_file is None:
            raise ValueError(
                "carte inexistante : un fichier est requis pour la créer"
            )  # already checked, should not happen
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
        with batch_file.file.open("rb") as source:
            with open_map_file(source) as data_source:
                map.expected_geometries = len(data_source[0])
            map.file.save(row.file, File(source), save=False)

    map.save()
    if batch_file:
        return task.replace(
            chain(
                process_map.si(map.id),
                complete_row.si(errors_by_line, batch_id, index, total, row.reference),
            )
        )
    else:
        # Metadata only update do not need map re-processing.
        return complete_row(errors_by_line, batch_id, index, total, row.reference)


@app.task
def complete_row(errors_by_line, batch_id, index, total, reference):
    """Log the successful import of a row and pass the errors on to the next one."""
    batch = MapImportBatch.objects.get(pk=batch_id)
    append_batch_log(batch, f"L'import {index + 1}/{total} a réussi : '{reference}'")
    return errors_by_line


@app.task(bind=True)
def generate_map_preview(task, map_id):
    logger.info(f"Starting preview generation on map {map_id}")

    map = Map.objects.get(pk=map_id)
    if map.zones.count() > 0:
        map.geometry = simplify_map(map)
    elif map.lines.count() > 0:
        map.geometry = simplify_lines(map)

    map.save()
