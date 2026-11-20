import csv
import logging
import uuid

from celery import chain
from celery.exceptions import Ignore
from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from config.celery_app import app
from envergo.geodata.import_batch import is_blank_row, is_file_valid, is_line_valid
from envergo.geodata.models import (
    IMPORT_LEASE,
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


class BatchImportInProgress(Exception):
    """Another run of the batch import is still alive."""


class MapImportInProgress(Exception):
    """Another live task is importing the map."""


# Map processing


def process_maps(map_ids):
    """Queue the geometry import of several maps, one after the other."""
    if map_ids:
        chain(*(process_map_signature(map_id) for map_id in map_ids)).apply_async(
            link_error=on_maps_chain_failure.s(list(map_ids))
        )


def process_map_signature(map_id, owner=None):
    """Signature of `process_map`, with the error callback failing its map.

    The task claims the map for itself, and fails if another live task holds it.
    A bigger process that has already claimed the map (see `claim_map`) passes
    its task id as `owner`, to hand its claim over to this task.
    """
    return process_map.si(map_id, owner=owner).on_error(
        on_map_failure.s(map_id, owner=owner)
    )


@app.task(bind=True, max_retries=1, dont_autoretry_for=(MapImportInProgress,))
def process_map(task, map_id, owner=None):
    """Replace the geometries of a map with the ones of its file."""
    logger.info(f"Starting import on map {map_id}")
    # The claim is committed on its own, so the admin page displays the progression.
    map = claim_map(map_id, task.request.id, owner=owner)

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
    # Only the import fields: metadata can be updated during processing (e.g. through admin interface).
    map.save(
        update_fields=[
            "geometry",
            "import_status",
            "task_id",
            "imported_geometries",
            "import_date",
        ]
    )

    if map.import_status == STATUSES.failure:
        notify_map_failure(map.id, "Aucune géométrie importée.")


@app.task
def on_map_failure(request, exc, traceback, map_id, owner=None):
    """Error callback of `process_map`: make sure a map never stays silently unprocessed."""
    mark_maps_failed([map_id], f"Erreur d'import ({exc})", owners=[request.id, owner])


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


def claim_map(map_id, task_id, owner=None):
    """Make the task the owner of the map import, and return the map."""
    with transaction.atomic():
        map = Map.objects.select_for_update().get(pk=map_id)
        if (
            map.task_id not in (None, task_id, owner)  # map is already claimed
            and map.import_date is not None
            and map.import_date
            > timezone.now() - IMPORT_LEASE  # the previous owner is not dead
        ):
            raise MapImportInProgress(
                f"Carte {map_id} en cours d'import par une autre tâche"
            )
        claim = {
            "task_id": task_id,
            "import_status": None,
            "import_error_msg": "",
            "import_date": timezone.now(),
        }
        Map.objects.filter(pk=map_id).update(**claim)
    map.refresh_from_db(fields=list(claim))
    return map


# Batch import
#
# A run owns the batch through `run_id`, renewed by each of its tasks: only one run
# is alive at a time, and the tasks of a replaced run stop on their own.
# The batch status is derived from its lines on every update, under the batch lock.


def start_batch_import(batch_id, only_failed=False):
    """Start a run of the batch import, unless one is still alive."""
    with transaction.atomic():
        batch = MapImportBatch.objects.select_for_update().get(pk=batch_id)
        if batch.is_running:
            raise BatchImportInProgress()
        run_id = str(uuid.uuid4())
        batch.run_id = run_id
        batch.run_updated_at = timezone.now()
        refresh_batch_status(batch)
        transaction.on_commit(
            process_map_import_batch_signature(batch_id, run_id, only_failed).delay
        )
    return run_id


def process_map_import_batch_signature(batch_id, run_id, only_failed=False):
    """Signature of `process_map_import_batch`, with the error callback failing its run."""
    return process_map_import_batch.si(
        batch_id, run_id, only_failed=only_failed
    ).on_error(on_batch_failure.s(batch_id, run_id))


@app.task(max_retries=0)
def process_map_import_batch(batch_id, run_id, only_failed=False):
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
    with transaction.atomic():
        batch = claim_batch_run(batch_id, run_id)

    errors = is_file_valid(batch.csv_file, batch.files)
    if errors:
        with transaction.atomic():
            batch = claim_batch_run(batch_id, run_id)
            fail_batch_before_import(batch, errors)
        notify_batch_failure(batch)
        return

    reader = csv.DictReader(read_csv_file(batch.csv_file))
    rows = [(reader.line_num, row) for row in reader if not is_blank_row(row)]
    with transaction.atomic():
        batch = claim_batch_run(batch_id, run_id)
        rows = reset_batch_lines(batch, rows, only_failed)
        if not rows:
            end_batch_run(batch)
    if not rows:
        notify_batch_end(batch)
        return

    chain(
        *(
            import_batch_row.si(batch_id, run_id, csv_line_number, raw_row)
            for csv_line_number, raw_row in rows
        ),
        finalize_batch.si(batch_id, run_id),
    ).apply_async(link_error=on_batch_chain_failure.s(batch_id, run_id))


@app.task(bind=True)
def import_batch_row(task, batch_id, run_id, csv_line_number, raw_row):
    """Create or update the Map described by a CSV row, and then process it if needed.

    A row failing validation, or whose map is imported by another task, is
    recorded on its line and skipped.
    Otherwise the map is saved: required columns always overwrite, optional
    ones only when non-empty, and a blank `departments` clears the field.
    A row with a file claims the map, replaces its file, then the task replaces
    itself with `process_map`, so the next row starts once the geometries are
    imported. A blank file cell only updates the metadata of an existing map.
    """
    with transaction.atomic():
        batch = claim_batch_run(batch_id, run_id)
    reference = (raw_row.get("reference") or "").strip()
    row, errors = is_line_valid(csv_line_number, raw_row, batch.files)
    if errors:
        set_batch_line_status(
            batch_id,
            run_id,
            csv_line_number,
            LINE_STATUSES.failure,
            reference=reference,
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
        # Nobody else knows the map before it is saved.
        map = Map(
            reference=row.reference,
            batch_created_at=now,
            task_id=task.request.id,
            import_date=now,
        )
    elif batch_file is not None:
        # Claimed before replacing its file, which another import may be reading.
        try:
            map = claim_map(map.id, task.request.id)
        except MapImportInProgress as exc:
            set_batch_line_status(
                batch_id,
                run_id,
                csv_line_number,
                LINE_STATUSES.failure,
                reference=reference,
                message=str(exc),
            )
            return None

    update_map_from_row(map, row)
    map.import_batch = batch
    map.batch_updated_at = now

    try:
        replaced_file_name = save_map_from_row(map, batch_file, row.file)
    except Exception as exc:
        if map.pk is not None and batch_file is not None:
            # Release the claim: the map must not look imported by a dead task.
            mark_maps_failed(
                [map.pk], f"Erreur d'import ({exc})", owners=[task.request.id]
            )
        raise
    if replaced_file_name:
        map.file.storage.delete(replaced_file_name)
    if batch_file:
        return task.replace(
            chain(
                process_map_signature(map.id, owner=task.request.id),
                complete_batch_row.si(batch_id, run_id, csv_line_number, row.reference),
            )
        )
    else:
        # Metadata only update do not need map re-processing.
        return complete_batch_row(batch_id, run_id, csv_line_number, row.reference)


@app.task
def complete_batch_row(batch_id, run_id, csv_line_number, reference):
    """Mark the line of a successfully imported row."""
    set_batch_line_status(
        batch_id, run_id, csv_line_number, LINE_STATUSES.success, reference=reference
    )


@app.task
def finalize_batch(batch_id, run_id):
    """Last task of the batch chain, once every row is imported."""
    with transaction.atomic():
        batch = claim_batch_run(batch_id, run_id)
        end_batch_run(batch)
    notify_batch_end(batch)


@app.task
def on_batch_failure(request, exc, traceback, batch_id, run_id):
    """Error callback of `process_map_import_batch`: a batch never stays silently in progress."""
    with transaction.atomic():
        batch = lock_batch_run(batch_id, run_id)
        if batch is None:
            return
        fail_batch_before_import(batch, [f"erreur inattendue ({exc})"])
    notify_batch_failure(batch)


@app.task
def on_batch_chain_failure(request, exc, traceback, batch_id, run_id):
    """Error callback of the batch chain: record the failure on the batch."""
    with transaction.atomic():
        batch = lock_batch_run(batch_id, run_id)
        if batch is None:
            # The callback is linked to every task of the chain: the first call
            # ends the run, the next ones have nothing left to do.
            return

        # Rows are processed one at a time: the first pending line is the one that broke.
        # The lines after it stay pending, so they can be retried on their own.
        line = batch.lines.filter(status=LINE_STATUSES.pending).first()
        if line is not None:
            line.status = LINE_STATUSES.failure
            line.message = f"erreur inattendue ({exc})"
            line.save()
        end_batch_run(batch)
    notify_batch_failure(batch)


def lock_batch_run(batch_id, run_id):
    """Lock and return the batch if `run_id` still owns it, None otherwise.

    Must be called in a transaction, which holds the lock.
    """
    return (
        MapImportBatch.objects.select_for_update()
        .filter(pk=batch_id, run_id=run_id)
        .first()
    )


def claim_batch_run(batch_id, run_id):
    """Lock the batch owned by the run, renew the run lease and return the batch.

    A task of a run replaced by another one is ignored: Celery stops its chain
    without recording a failure. Must be called in a transaction.
    """
    batch = lock_batch_run(batch_id, run_id)
    if batch is None:
        logger.info(f"Run {run_id} of map batch {batch_id} is over, task ignored")
        raise Ignore()
    batch.run_updated_at = timezone.now()
    batch.save(update_fields=["run_updated_at"])
    return batch


def end_batch_run(batch):
    """Release the batch from its run, and set its final status. The batch is locked."""
    batch.run_id = None
    batch.run_updated_at = None
    refresh_batch_status(batch)


def refresh_batch_status(batch):
    """Derive the batch status from its run and its lines, and save it."""
    lines = batch.lines.all()
    if batch.run_id is not None:
        batch.import_status = None
    elif not lines.exclude(status=LINE_STATUSES.success).exists():
        batch.import_status = STATUSES.success
    elif lines.filter(status=LINE_STATUSES.success).exists():
        batch.import_status = STATUSES.partial_success
    else:
        batch.import_status = STATUSES.failure
    batch.import_date = timezone.now()
    batch.save(
        update_fields=["run_id", "run_updated_at", "import_status", "import_date"]
    )


def notify_batch_end(batch):
    if batch.import_status == STATUSES.failure:
        notify_batch_failure(batch)


def fail_batch_before_import(batch, errors):
    """Fail a batch before any of its rows is imported, recording the errors on line 0."""
    batch.lines.all().delete()
    batch.lines.create(
        line_number=0, status=LINE_STATUSES.failure, message="\n".join(errors)
    )
    end_batch_run(batch)


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


def save_map_from_row(map, batch_file, file_name):
    """Save the map, with the batch file as its new file if any.

    Return the name of the replaced file, to delete once the map is saved.
    """
    replaced_file_name = None
    if batch_file is not None:
        replaced_file_name = map.file.name
        with batch_file.file.open("rb") as source:
            with open_map_file(source) as data_source:
                map.expected_geometries = len(data_source[0])
            map.file.save(file_name, File(source), save=False)

    try:
        map.save()
    except Exception:
        # The new file is already stored but nothing references it.
        if batch_file is not None:
            map.file.storage.delete(map.file.name)
        raise
    return replaced_file_name


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


def set_batch_line_status(
    batch_id, run_id, csv_line_number, status, reference="", message=""
):
    """Record the outcome of a CSV line, then refresh the batch status.

    The progress survives a broken chain.
    """
    with transaction.atomic():
        batch = claim_batch_run(batch_id, run_id)
        MapImportBatchLine.objects.update_or_create(
            batch=batch,
            line_number=csv_line_number,
            defaults={"status": status, "reference": reference, "message": message},
        )
        refresh_batch_status(batch)


# Status and notification helpers


def mark_maps_failed(map_ids, error, owners=()):
    """Mark maps as failed with an error message, and detach them from their task.

    Maps owned by another live task than `owners` are left untouched.
    """
    not_owned = (
        Q(task_id__isnull=True)
        | Q(task_id__in=[owner for owner in owners if owner])
        | Q(import_date__isnull=True)
        | Q(import_date__lt=timezone.now() - IMPORT_LEASE)
    )
    Map.objects.filter(not_owned, pk__in=map_ids).update(
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
