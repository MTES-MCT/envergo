import csv
import logging

from celery import chain
from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from config.celery_app import app
from envergo.geodata.import_batch import is_blank_row, is_file_valid, is_line_valid
from envergo.geodata.models import (
    LINE_STATUSES,
    STATUSES,
    Map,
    MapImportBatch,
    MapImportBatchLine,
)
from envergo.geodata.utils import (
    make_polygons_valid,
    open_map_file,
    process_lines_file,
    process_zones_file,
    read_csv_file,
    simplify_lines,
    simplify_map,
)
from envergo.utils.tchap import notify
from envergo.utils.tools import get_base_url

logger = logging.getLogger(__name__)


# Map processing


def process_maps(map_ids):
    """Queue the geometry import of several maps, one after the other."""
    if map_ids:
        chain(*(process_map_signature(map_id) for map_id in map_ids)).apply_async(
            link_error=on_maps_chain_failure.s(list(map_ids))
        )


def process_map_signature(map_id):
    """Signature of `process_map`, with the error callback failing its map."""
    return process_map.si(map_id).on_error(on_map_failure.s(map_id))


@app.task(bind=True, max_retries=1)
def process_map(task, map_id):
    """Replace the geometries of a map with the ones of its file."""
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

    if map.import_status == STATUSES.failure:
        notify_map_failure(map.id, "Aucune géométrie importée.")


@app.task
def on_map_failure(request, exc, traceback, map_id):
    """Error callback of `process_map`: make sure a map never stays silently unprocessed."""
    mark_maps_failed([map_id], f"Erreur d'import ({exc})")


@app.task
def on_maps_chain_failure(request, exc, traceback, map_ids):
    """Error callback of the `process_maps` chain.

    Every map queued after the failed one is marked as failed, and a single
    summary is notified. The failed map itself is marked by `on_map_failure`.
    """
    failed_id = request.args[0]
    next_index = map_ids.index(failed_id) + 1
    skipped_ids = map_ids[next_index:]

    mark_maps_failed(
        skipped_ids,
        f"Import non effectué : l'import de la carte {failed_id} a échoué avant",
    )
    notify_map_failure(failed_id, f"Erreur d'import ({exc})", skipped_ids)


# Batch import


@app.task(max_retries=0)
def process_map_import_batch(batch_id, only_failed=False):
    """Create or update Map objects described in a batch CSV.

    The CSV is validated first: any error fails the batch before any import.
    Rows are then imported one at a time in a sequential chain, each row
    recording its outcome on a MapImportBatchLine.
    A row that fails validation again is recorded and skipped.
    Any other error, timeouts included, stops the chain and mark the batch as failed.

    With `only_failed`, the lines already imported are kept and only the
    other rows are processed again.
    """
    logger.info(f"Starting import on map batch {batch_id}")

    batch = MapImportBatch.objects.get(pk=batch_id)
    batch.import_status = None
    batch.import_date = timezone.now()
    batch.save(update_fields=["import_status", "import_date"])

    errors = is_file_valid(batch.csv_file, batch.files)
    if errors:
        fail_invalid_batch(batch, errors)
        return

    reader = csv.DictReader(read_csv_file(batch.csv_file))
    rows = [(reader.line_num, row) for row in reader if not is_blank_row(row)]
    rows = reset_batch_lines(batch, rows, only_failed)
    if not rows:
        set_batch_final_status(batch)
        return

    chain(
        *(
            import_batch_row.si(batch_id, csv_line_number, raw_row)
            for csv_line_number, raw_row in rows
        ),
        finalize_batch.si(batch_id),
    ).apply_async(link_error=on_batch_chain_failure.s(batch_id))


@app.task(bind=True)
def import_batch_row(task, batch_id, csv_line_number, raw_row):
    """Create or update the Map described by a CSV row, and then process it if needed.

    A row failing validation is recorded on its line and skipped.
    Otherwise the map is saved: required columns always overwrite, optional
    ones only when non-empty, and a blank `departments` clears the field.
    A row with a file replaces the map's file; a blank file cell only updates
    the metadata of an existing map. The task then replaces itself with
    `process_map`, so the next row starts once the geometries are imported.
    """
    batch = MapImportBatch.objects.get(pk=batch_id)
    row, errors = is_line_valid(csv_line_number, raw_row, batch.files)
    if errors:
        set_batch_line_status(
            batch,
            csv_line_number,
            LINE_STATUSES.failure,
            reference=(raw_row.get("reference") or "").strip(),
            message=" ; ".join(errors),
        )
        return None

    now = timezone.now()

    map = Map.objects.filter(reference=row.reference).first()
    batch_file = batch.files.filter(name=row.file).first()
    if map is None:
        if batch_file is None:
            raise ValueError(
                "carte inexistante : un fichier est requis pour la créer"
            )  # already checked, should not happen
        map = Map(reference=row.reference, batch_created_at=now)

    update_map_from_row(map, row)
    map.import_batch = batch
    map.batch_updated_at = now

    replaced_file_name = None
    if batch_file is not None:
        replaced_file_name = map.file.name
        with batch_file.file.open("rb") as source:
            with open_map_file(source) as data_source:
                map.expected_geometries = len(data_source[0])
            map.file.save(row.file, File(source), save=False)

    try:
        map.save()
    except Exception:
        # The new file is already stored but nothing references it.
        if batch_file is not None:
            map.file.storage.delete(map.file.name)
        raise
    if replaced_file_name:
        map.file.storage.delete(replaced_file_name)
    if batch_file:
        return task.replace(
            chain(
                process_map_signature(map.id),
                complete_batch_row.si(batch_id, csv_line_number, row.reference),
            )
        )
    else:
        # Metadata only update do not need map re-processing.
        return complete_batch_row(batch_id, csv_line_number, row.reference)


@app.task
def complete_batch_row(batch_id, csv_line_number, reference):
    """Mark the line of a successfully imported row."""
    batch = MapImportBatch.objects.get(pk=batch_id)
    set_batch_line_status(
        batch, csv_line_number, LINE_STATUSES.success, reference=reference
    )
    if batch.import_status is None:
        batch.import_status = STATUSES.partial_success
        batch.save(update_fields=["import_status"])


@app.task
def finalize_batch(batch_id):
    """Last task of the batch chain, once every row is imported."""
    set_batch_final_status(MapImportBatch.objects.get(pk=batch_id))


@app.task
def on_batch_chain_failure(request, exc, traceback, batch_id):
    """Error callback of the batch chain: record the failure on the batch."""
    batch = MapImportBatch.objects.get(pk=batch_id)
    if batch.import_status == STATUSES.failure:
        # The callback is linked to every task of the chain: only the first
        # call describes the failure.
        return

    # Rows are processed one at a time: the first pending line is the one that broke.
    # The lines after it stay pending, so they can be retried on their own.
    line = batch.lines.filter(status=LINE_STATUSES.pending).first()
    if line is not None:
        line.status = LINE_STATUSES.failure
        line.message = f"erreur inattendue ({exc})"
        line.save()

    batch.import_status = STATUSES.failure
    batch.import_date = timezone.now()
    batch.save(update_fields=["import_status", "import_date"])
    notify_batch_failure(batch)


def fail_invalid_batch(batch, errors):
    """Fail a batch whose CSV is invalid, before any import."""
    batch.lines.all().delete()
    batch.lines.create(
        line_number=0, status=LINE_STATUSES.failure, message="\n".join(errors)
    )
    batch.import_status = STATUSES.failure
    batch.import_date = timezone.now()
    batch.save(update_fields=["import_status", "import_date"])
    notify_batch_failure(batch)


def reset_batch_lines(batch, rows, only_failed):
    """Create a pending line for each row to import, and return these rows.

    With `only_failed`, the successful lines are kept and their rows skipped.
    """
    if only_failed:
        done = set(
            batch.lines.filter(status=LINE_STATUSES.success).values_list(
                "line_number", flat=True
            )
        )
        batch.lines.exclude(line_number__in=done).delete()
    else:
        done = set()
        batch.lines.all().delete()

    rows = [
        (csv_line_number, row)
        for csv_line_number, row in rows
        if csv_line_number not in done
    ]
    MapImportBatchLine.objects.bulk_create(
        MapImportBatchLine(batch=batch, line_number=csv_line_number)
        for csv_line_number, _ in rows
    )
    return rows


def update_map_from_row(map, row):
    """Copy the columns of a valid row on its map, without saving it."""
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


def set_batch_line_status(batch, csv_line_number, status, reference="", message=""):
    """Record the outcome of a CSV line, so the progress survives a broken chain."""
    MapImportBatchLine.objects.update_or_create(
        batch=batch,
        line_number=csv_line_number,
        defaults={"status": status, "reference": reference, "message": message},
    )


def set_batch_final_status(batch):
    """Set the batch status from the outcome of its lines."""
    if not batch.lines.exclude(status=LINE_STATUSES.success).exists():
        batch.import_status = STATUSES.success
    elif batch.lines.filter(status=LINE_STATUSES.success).exists():
        batch.import_status = STATUSES.partial_success
    else:
        batch.import_status = STATUSES.failure
    batch.import_date = timezone.now()
    batch.save(update_fields=["import_status", "import_date"])
    if batch.import_status == STATUSES.failure:
        notify_batch_failure(batch)


# Status and notification helpers


def mark_maps_failed(map_ids, error):
    """Mark maps as failed with an error message, and detach them from their task."""
    Map.objects.filter(pk__in=map_ids).update(
        import_status=STATUSES.failure,
        import_error_msg=error,
        import_date=timezone.now(),
        task_id=None,
    )


def notify_map_failure(map_id, error, skipped_ids=()):
    """Warn the cartographers of a failed map, and of the maps skipped after it."""
    base_url = get_base_url(settings.ENVERGO_AMENAGEMENT_DOMAIN)

    def map_link(map_id):
        return {
            "id": map_id,
            "url": base_url + reverse("admin:geodata_map_change", args=[map_id]),
        }

    message = render_to_string(
        "geodata/mattermost_map_import_failure.txt",
        context={
            "failed": map_link(map_id),
            "error": error,
            "skipped": [map_link(skipped_id) for skipped_id in skipped_ids],
            "handlers": settings.CARTO_NOTIFICATION_HANDLERS,
        },
    )
    notify(message, "amenagement")


def notify_batch_failure(batch):
    """Warn the cartographers of a failed batch import, with its summary."""
    base_url = get_base_url(settings.ENVERGO_AMENAGEMENT_DOMAIN)
    message = render_to_string(
        "geodata/mattermost_batch_import_failure.txt",
        context={
            "batch_id": batch.id,
            "batch_url": base_url
            + reverse("admin:geodata_mapimportbatch_change", args=[batch.id]),
            "summary": batch.import_summary,
            "handlers": settings.CARTO_NOTIFICATION_HANDLERS,
        },
    )
    notify(message, "amenagement")


# Preview


@app.task(bind=True)
def generate_map_preview(task, map_id):
    logger.info(f"Starting preview generation on map {map_id}")

    map = Map.objects.get(pk=map_id)
    if map.zones.count() > 0:
        map.geometry = simplify_map(map)
    elif map.lines.count() > 0:
        map.geometry = simplify_lines(map)

    map.save()
