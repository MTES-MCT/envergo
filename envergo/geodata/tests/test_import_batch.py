import shutil
import zipfile
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import modelform_factory
from django.urls import reverse

from envergo.geodata.admin import MapImportBatchForm
from envergo.geodata.import_batch import parse_batch_row, validate_headers
from envergo.geodata.models import (
    LINE_STATUSES,
    STATUSES,
    Map,
    MapImportBatch,
    MapImportBatchFile,
)
from envergo.geodata.tasks import (
    complete_row,
    finalize_batch,
    import_batch_row,
    process_map,
    process_map_import_batch,
)
from envergo.geodata.tests.factories import (
    MapFactory,
    MapImportBatchFactory,
    MapImportBatchFileFactory,
)

pytestmark = pytest.mark.django_db

CSV_HEADER = "reference,file,name,description,departments"

# A real geopackage, so libmagic detects a sqlite database and not plain text
GPKG_TEMPLATE = "envergo/static/gpkg/hedge_data_export_template.gpkg"


def make_gpkg(tmp_path, filename):
    """Return the path to a file libmagic recognizes as a geopackage."""
    path = tmp_path / filename
    shutil.copy(GPKG_TEMPLATE, path)
    return path


def make_batch(csv_content, filenames=()):
    batch = MapImportBatchFactory(csv_file__data=csv_content.encode())
    for filename in filenames:
        MapImportBatchFileFactory(batch=batch, name=filename, file__filename=filename)
    return batch


def make_batch_form(upload):
    """Build the admin form the way the ModelAdmin does (it injects the model)."""
    form_class = modelform_factory(
        MapImportBatch, form=MapImportBatchForm, fields=["name", "csv_file"]
    )
    return form_class(data={"name": "Lot"}, files={"csv_file": upload})


@contextmanager
def fake_open_map_file(file):
    yield [range(42)]


def run_task(batch, only_failed=False):
    """Run the whole batch chain eagerly and return the ids of processed maps.

    `process_map` is stubbed: its geometry import is tested on its own.
    """
    processed = []
    with (
        patch("envergo.geodata.tasks.open_map_file", fake_open_map_file),
        patch.object(process_map, "run", side_effect=processed.append),
    ):
        process_map_import_batch.apply(args=(batch.id, only_failed))
    batch.refresh_from_db()
    return processed


def line_statuses(batch):
    return [
        (line.line_number, line.reference, line.status) for line in batch.lines.all()
    ]


def test_validate_headers_reports_missing_columns():
    errors = validate_headers(["reference", "file"])
    assert len(errors) == 1
    assert "name" in errors[0]
    assert "description" in errors[0]
    assert "departments" in errors[0]

    assert validate_headers(CSV_HEADER.split(",")) == []
    assert validate_headers(None)

    # `file` is optional: a metadata-only update CSV need not include it.
    assert validate_headers(["reference", "name", "description", "departments"]) == []


def test_parse_batch_row_requires_reference_and_name():
    row = {"reference": "", "file": "a.gpkg", "name": "N", "description": ""}
    _, errors = parse_batch_row(2, row)
    assert "référence manquante" in errors[0]

    # A blank file is legitimate (metadata-only update), so it parses.
    row = {"reference": "r1", "file": " ", "name": "N", "description": "desc"}
    parsed, errors = parse_batch_row(2, row)
    assert errors == []
    assert parsed.file == ""

    row = {"reference": "r1", "file": "a.gpkg", "name": "", "description": ""}
    _, errors = parse_batch_row(2, row)
    assert "nom de carte manquant" in errors[0]


def test_parse_batch_row_requires_description():
    """A blank description would silently erase an existing map's one."""
    row = {
        "reference": "r1",
        "file": "a.gpkg",
        "name": "N",
        "description": "  ",
        "departments": "44",
    }
    _, errors = parse_batch_row(2, row)
    assert "description manquante" in errors[0]


def test_blank_departments_means_no_department():
    """An empty departments cell is legitimate."""
    row = {
        "reference": "r1",
        "file": "a.gpkg",
        "name": "N",
        "description": "desc",
        "departments": "",
    }
    parsed, errors = parse_batch_row(2, row)
    assert errors == []
    assert parsed.departments == []


def test_update_does_not_silently_wipe_description():
    existing = MapFactory(
        reference="r1", description="Description existante", departments=["44", "56"]
    )
    csv_content = f"{CSV_HEADER}\nr1,a.gpkg,Nouveau nom,,44\n"
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    run_task(batch)

    existing.refresh_from_db()
    assert batch.import_status == STATUSES.failure
    assert "description manquante" in batch.lines.get().message
    assert existing.description == "Description existante"
    assert existing.departments == ["44", "56"]


def test_update_clears_departments_when_cell_is_blank():
    existing = MapFactory(reference="r1", departments=["44", "56"])
    csv_content = f"{CSV_HEADER}\nr1,a.gpkg,Nom,Description,\n"
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    run_task(batch)

    existing.refresh_from_db()
    assert batch.import_status == STATUSES.success
    assert existing.departments is None


def test_parse_batch_row_validates_choices():
    row = {
        "reference": "r1",
        "file": "a.gpkg",
        "name": "N",
        "description": "desc",
        "map_type": "nope",
    }
    _, errors = parse_batch_row(2, row)
    assert "map_type inconnu" in errors[0]

    row["map_type"] = "zone_humide"
    row["data_type"] = "nope"
    _, errors = parse_batch_row(2, row)
    assert "data_type inconnu" in errors[0]

    row["data_type"] = "certain"
    row["display_for_user"] = "nope"
    _, errors = parse_batch_row(2, row)
    assert "display_for_user invalide" in errors[0]


def test_parse_batch_row_normalises_values():
    row = {
        "reference": " r1 ",
        "file": "a.gpkg",
        "name": "Zones humides 44",
        "description": "desc",
        "departments": "44, 56",
        "display_for_user": "FALSE",
    }
    parsed, errors = parse_batch_row(2, row)
    assert not errors
    assert parsed.reference == "r1"
    assert parsed.departments == ["44", "56"]
    assert parsed.display_for_user is False


def test_batch_with_missing_columns_fails_without_touching_maps():
    batch = make_batch("reference,file\nr1,a.gpkg\n")
    queued = run_task(batch)

    assert batch.import_status == STATUSES.failure
    assert "Colonnes manquantes" in batch.lines.get(line_number=0).message
    assert Map.objects.count() == 0
    assert len(queued) == 0


def test_batch_creates_maps():
    csv_content = (
        f"{CSV_HEADER},map_type\n"
        'r1,a.gpkg,Carte A,Description A,"44,56",zone_humide\n'
        "r2,b.gpkg,Carte B,Description B,29,zone_inondable\n"
    )
    batch = make_batch(csv_content, filenames=["a.gpkg", "b.gpkg"])
    queued = run_task(batch)

    assert batch.import_status == STATUSES.success
    assert batch.import_summary.splitlines() == [
        "2/2 ligne(s) importée(s).",
        "L'import 1/2 (ligne 2) a réussi : 'r1'.",
        "L'import 2/2 (ligne 3) a réussi : 'r2'.",
    ]
    assert line_statuses(batch) == [
        (2, "r1", LINE_STATUSES.success),
        (3, "r2", LINE_STATUSES.success),
    ]

    map_a = Map.objects.get(reference="r1")
    assert map_a.name == "Carte A"
    assert map_a.description == "Description A"
    assert map_a.departments == ["44", "56"]
    assert map_a.map_type == "zone_humide"
    assert map_a.import_batch == batch
    assert map_a.batch_created_at is not None
    assert map_a.batch_updated_at is not None
    assert map_a.expected_geometries == 42
    assert map_a.file.name.startswith("maps/")

    assert Map.objects.filter(reference="r2").exists()
    assert len(queued) == 2


def test_batch_updates_existing_map():
    existing = MapFactory(
        reference="r1",
        name="Ancien nom",
        display_name="Nom d'affichage",
        batch_created_at=None,
    )
    csv_content = f"{CSV_HEADER}\nr1,a.gpkg,Nouveau nom,Nouvelle description,44\n"
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    queued = run_task(batch)

    assert batch.import_status == STATUSES.success

    existing.refresh_from_db()
    assert existing.name == "Nouveau nom"
    assert existing.description == "Nouvelle description"
    # Optional columns don't overwrite when the cell is blank
    assert existing.display_name == "Nom d'affichage"
    assert existing.batch_created_at is None
    assert existing.batch_updated_at is not None
    assert existing.import_batch == batch
    assert Map.objects.count() == 1
    assert len(queued) == 1


def test_batch_metadata_only_update_skips_reimport():
    """A blank file cell updates the map's fields without re-importing it."""
    existing = MapFactory(
        reference="r1",
        name="Ancien nom",
        description="Ancienne description",
        expected_geometries=7,
    )
    original_file = existing.file.name

    csv_content = f"{CSV_HEADER}\nr1,,Nouveau nom,Nouvelle description,44\n"
    batch = make_batch(csv_content)
    queued = []
    with (
        patch("envergo.geodata.tasks.open_map_file") as mock_open,
        patch.object(process_map, "run", side_effect=queued.append),
    ):
        process_map_import_batch.apply(args=(batch.id,))
    batch.refresh_from_db()

    assert batch.import_status == STATUSES.success
    existing.refresh_from_db()
    assert existing.name == "Nouveau nom"
    assert existing.description == "Nouvelle description"
    assert existing.departments == ["44"]
    # Geometry is left untouched: no re-import, no re-copy, no recount.
    assert len(queued) == 0
    assert mock_open.call_count == 0
    assert existing.expected_geometries == 7
    assert existing.file.name == original_file


def test_batch_metadata_only_update_without_file_column():
    """A pure update CSV can omit the file column entirely."""
    existing = MapFactory(reference="r1", name="Ancien nom")
    csv_content = (
        "reference,name,description,departments\n"
        "r1,Nouveau nom,Nouvelle description,44\n"
    )
    batch = make_batch(csv_content)
    queued = run_task(batch)

    assert batch.import_status == STATUSES.success
    existing.refresh_from_db()
    assert existing.name == "Nouveau nom"
    assert len(queued) == 0


def test_batch_metadata_only_update_requires_existing_map():
    """A blank file cell cannot create a map: a file is required for that."""
    csv_content = f"{CSV_HEADER}\nr1,,Nouveau nom,Nouvelle description,44\n"
    batch = make_batch(csv_content)
    queued = run_task(batch)

    assert batch.import_status == STATUSES.failure
    assert "fichier manquant pour une carte inexistante" in batch.lines.get().message
    assert Map.objects.count() == 0
    assert len(queued) == 0


def test_batch_mixes_import_and_metadata_only_update():
    """Only rows carrying a file re-import their geometry."""
    MapFactory(reference="r2", name="Ancien nom")
    csv_content = (
        f"{CSV_HEADER}\n"
        "r1,a.gpkg,Carte A,Description A,44\n"
        "r2,,Nom mis à jour,Description mise à jour,56\n"
    )
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    queued = run_task(batch)

    assert batch.import_status == STATUSES.success
    assert len(queued) == 1
    assert Map.objects.get(reference="r2").name == "Nom mis à jour"


def test_batch_reimport_deletes_the_replaced_file():
    """A re-imported map keeps only its new file in the storage."""
    existing = MapFactory(reference="r1")
    storage = existing.file.storage
    old_name = storage.save("maps/old.gpkg", ContentFile(b"old"))
    Map.objects.filter(pk=existing.pk).update(file=old_name)
    batch = make_batch(
        f"{CSV_HEADER}\nr1,a.gpkg,Carte A,Description A,44\n", filenames=["a.gpkg"]
    )
    run_task(batch)

    existing.refresh_from_db()
    assert existing.file.name != old_name
    assert storage.exists(existing.file.name)
    assert not storage.exists(old_name)


def test_batch_row_deletes_its_new_file_when_the_save_fails():
    """No unreferenced file is left behind by a failed save."""
    existing = MapFactory(reference="r1")
    storage = existing.file.storage
    old_name = storage.save("maps/old.gpkg", ContentFile(b"old"))
    Map.objects.filter(pk=existing.pk).update(file=old_name)
    batch = make_batch(
        f"{CSV_HEADER}\nr1,a.gpkg,Carte A,Description A,44\n", filenames=["a.gpkg"]
    )
    stored = []
    original_save = storage.save

    def tracking_save(*args, **kwargs):
        stored.append(original_save(*args, **kwargs))
        return stored[-1]

    with (
        patch("envergo.geodata.tasks.open_map_file", fake_open_map_file),
        patch.object(storage, "save", tracking_save),
        patch.object(Map, "save", side_effect=RuntimeError("db down")),
    ):
        with pytest.raises(RuntimeError):
            import_batch_row.run(
                batch.id,
                2,
                {
                    "reference": "r1",
                    "file": "a.gpkg",
                    "name": "Carte A",
                    "description": "Description A",
                    "departments": "44",
                },
            )

    assert stored
    assert not any(storage.exists(name) for name in stored)
    assert storage.exists(old_name)


def test_batch_with_invalid_csv_imports_nothing():
    """The CSV is validated as a whole: one bad row rejects the batch.

    Every problem is listed under a summary line, with the line number of the
    operator's file (blank lines included).
    """
    csv_content = (
        f"{CSV_HEADER},map_type\n"
        "r0,a.gpkg,Carte 0,Description 0,44,nope\n"
        "\n"
        "r1,missing.gpkg,Carte A,Description A,29,\n"
        "r1,a.gpkg,Carte A bis,Description bis,56,\n"
    )
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    processed = run_task(batch)

    assert batch.import_status == STATUSES.failure
    assert (
        batch.import_summary.splitlines()[0] == "Aucune ligne importée, csv non valide."
    )
    messages = batch.lines.get(line_number=0).message.splitlines()
    assert len(messages) == 3
    assert messages[0].startswith("Ligne 2") and "map_type inconnu" in messages[0]
    assert messages[1].startswith("Ligne 4") and "missing.gpkg" in messages[1]
    assert messages[2].startswith("Ligne 5") and "référence en double" in messages[2]
    assert Map.objects.count() == 0
    assert processed == []


def test_batch_blank_rows_are_skipped():
    csv_content = f"{CSV_HEADER}\nr1,a.gpkg,Carte A,Description A,44\n,,,,\n"
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    run_task(batch)

    assert batch.import_status == STATUSES.success
    assert Map.objects.count() == 1


def test_batch_is_failed_when_a_map_processing_crashes():
    """A crash in process_map stops the chain: the batch must not stay pending."""
    csv_content = (
        f"{CSV_HEADER}\n"
        "r1,a.gpkg,Carte A,Description A,44\n"
        "r2,b.gpkg,Carte B,Description B,29\n"
    )
    batch = make_batch(csv_content, filenames=["a.gpkg", "b.gpkg"])

    with (
        patch("envergo.geodata.tasks.open_map_file", fake_open_map_file),
        patch.object(process_map, "run", side_effect=RuntimeError("boom")),
        patch.object(process_map, "max_retries", 0),
    ):
        process_map_import_batch.apply(args=(batch.id,))
    batch.refresh_from_db()

    assert batch.import_status == STATUSES.failure
    # The crash happens while processing the first map: its line is the one
    # failing, the next one stays pending so a retry can pick it up.
    assert line_statuses(batch) == [
        (2, "", LINE_STATUSES.failure),
        (3, "", LINE_STATUSES.pending),
    ]
    assert batch.lines.get(line_number=2).message == "erreur inattendue (boom)"
    assert batch.import_summary.splitlines() == [
        "Import interrompu à la ligne 1/2 par une erreur inattendue, "
        "1 ligne(s) non traitée(s).",
        "L'import 1/2 (ligne 2) a échoué : erreur inattendue (boom).",
    ]
    assert batch.import_date is not None
    # The chain stopped at the first map.
    assert Map.objects.filter(reference="r2").count() == 0


def test_import_batch_row_records_errors_on_its_line_and_skips_the_row():
    """A row failing validation is recorded on its line, and no map is created."""
    batch = make_batch(f"{CSV_HEADER}\n")
    raw_row = {
        "reference": "r1",
        "file": "missing.gpkg",
        "name": "Carte A",
        "description": "Description A",
        "departments": "44",
    }

    import_batch_row.apply(args=(batch.id, 2, raw_row)).get()

    line = batch.lines.get(line_number=2)
    assert line.status == LINE_STATUSES.failure
    assert line.reference == "r1"
    assert "missing.gpkg" in line.message
    assert Map.objects.count() == 0


def test_import_summary_counts_the_lines_and_the_interruption():
    batch = make_batch(f"{CSV_HEADER}\n")
    batch.lines.create(line_number=2, reference="r1", status=LINE_STATUSES.success)
    batch.lines.create(line_number=3, status=LINE_STATUSES.failure, message="x")
    batch.lines.create(line_number=4, status=LINE_STATUSES.pending)
    batch.import_status = STATUSES.failure
    batch.save()

    assert batch.import_summary.splitlines() == [
        "Import interrompu à la ligne 2/3 par une erreur inattendue, "
        "1 ligne(s) non traitée(s).",
        "L'import 1/3 (ligne 2) a réussi : 'r1'.",
        "L'import 2/3 (ligne 3) a échoué : x.",
    ]


@pytest.mark.parametrize(
    "statuses,expected",
    [
        ([], STATUSES.success),
        ([LINE_STATUSES.success, LINE_STATUSES.success], STATUSES.success),
        ([LINE_STATUSES.success, LINE_STATUSES.failure], STATUSES.partial_success),
        ([LINE_STATUSES.failure, LINE_STATUSES.failure], STATUSES.failure),
    ],
)
def test_finalize_batch_status(statuses, expected):
    batch = make_batch(f"{CSV_HEADER}\n")
    for line_number, status in enumerate(statuses, start=2):
        batch.lines.create(line_number=line_number, status=status)

    finalize_batch.apply(args=(batch.id,))
    batch.refresh_from_db()

    assert batch.import_status == expected


def test_batch_rerun_all_replaces_the_previous_lines():
    csv_content = f"{CSV_HEADER}\nr1,a.gpkg,Carte A,Description A,44\n"
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    batch.lines.create(line_number=2, reference="r1", status=LINE_STATUSES.success)
    batch.lines.create(line_number=7, status=LINE_STATUSES.failure)

    run_task(batch)

    assert batch.import_status == STATUSES.success
    assert line_statuses(batch) == [(2, "r1", LINE_STATUSES.success)]


def test_batch_retry_failed_lines_skips_the_imported_ones():
    csv_content = (
        f"{CSV_HEADER}\n"
        "r1,a.gpkg,Carte A,Description A,44\n"
        "r2,b.gpkg,Carte B,Description B,29\n"
    )
    batch = make_batch(csv_content, filenames=["a.gpkg", "b.gpkg"])
    batch.lines.create(line_number=2, reference="r1", status=LINE_STATUSES.success)
    batch.lines.create(line_number=3, reference="r2", status=LINE_STATUSES.failure)
    batch.import_status = STATUSES.partial_success
    batch.save()

    processed = run_task(batch, only_failed=True)

    # r1 was already imported: it is neither processed nor created again.
    assert Map.objects.filter(reference="r1").exists() is False
    assert processed == [Map.objects.get(reference="r2").id]
    assert batch.import_status == STATUSES.success
    assert line_statuses(batch) == [
        (2, "r1", LINE_STATUSES.success),
        (3, "r2", LINE_STATUSES.success),
    ]


def test_imported_row_marks_the_batch_partial_success():
    """An interrupted run keeps a status once one row is imported."""
    batch = make_batch(f"{CSV_HEADER}\n")
    batch.lines.create(line_number=2, reference="r1")

    complete_row.apply(args=(batch.id, 2, "r1"))
    batch.refresh_from_db()

    assert batch.import_status == STATUSES.partial_success
    assert batch.lines.get(line_number=2).status == LINE_STATUSES.success


def test_row_failing_validation_keeps_the_batch_unprocessed():
    batch = make_batch(f"{CSV_HEADER}\n")
    raw_row = {
        "reference": "r1",
        "file": "missing.gpkg",
        "name": "Carte A",
        "description": "Description A",
        "departments": "44",
    }

    import_batch_row.apply(args=(batch.id, 2, raw_row)).get()
    batch.refresh_from_db()

    assert batch.import_status is None


class TestUploadView:
    def upload_url(self, batch):
        return reverse("admin:geodata_mapimportbatch_upload", args=[batch.pk])

    def test_upload_creates_batch_file(self, admin_client, tmp_path):
        batch = MapImportBatchFactory()
        gpkg = make_gpkg(tmp_path, "carte.gpkg")

        with open(gpkg, "rb") as f:
            res = admin_client.post(self.upload_url(batch), {"map_files": f})

        assert res.status_code == 200
        batch_file = MapImportBatchFile.objects.get(batch=batch)
        assert batch_file.name == "carte.gpkg"
        assert res.json() == {"id": batch_file.id}

    def test_upload_accepts_zip(self, admin_client, tmp_path):
        batch = MapImportBatchFactory()
        archive = tmp_path / "carte.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("carte.shp", "x" * 200)

        with open(archive, "rb") as f:
            res = admin_client.post(self.upload_url(batch), {"map_files": f})

        assert res.status_code == 200
        assert MapImportBatchFile.objects.count() == 1

    def test_upload_rejects_content_not_matching_extension(
        self, admin_client, tmp_path
    ):
        """A text file renamed to .gpkg must not pass as a geopackage."""
        batch = MapImportBatchFactory()
        fake = tmp_path / "carte.gpkg"
        fake.write_bytes(b"this is definitely not a geopackage")

        with open(fake, "rb") as f:
            res = admin_client.post(self.upload_url(batch), {"map_files": f})

        assert res.status_code == 400
        assert "ne correspond pas" in res.json()["error"]
        assert MapImportBatchFile.objects.count() == 0

    def test_upload_rejects_zip_renamed_as_gpkg(self, admin_client, tmp_path):
        batch = MapImportBatchFactory()
        fake = tmp_path / "carte.gpkg"
        with zipfile.ZipFile(fake, "w") as z:
            z.writestr("carte.shp", "x" * 200)

        with open(fake, "rb") as f:
            res = admin_client.post(self.upload_url(batch), {"map_files": f})

        assert res.status_code == 400
        assert MapImportBatchFile.objects.count() == 0

    def test_upload_rejects_duplicate_filename(self, admin_client, tmp_path):
        batch = MapImportBatchFactory()
        MapImportBatchFileFactory(batch=batch, name="carte.gpkg")
        gpkg = make_gpkg(tmp_path, "carte.gpkg")

        with open(gpkg, "rb") as f:
            res = admin_client.post(self.upload_url(batch), {"map_files": f})

        assert res.status_code == 400
        assert "déjà été téléversé" in res.json()["error"]

    def test_upload_retry_of_completed_upload_returns_existing_file(
        self, admin_client, tmp_path
    ):
        """The first response may have been lost: the retry must succeed."""
        batch = MapImportBatchFactory()
        gpkg = make_gpkg(tmp_path, "carte.gpkg")
        with open(gpkg, "rb") as f:
            first = admin_client.post(self.upload_url(batch), {"map_files": f})
        with open(gpkg, "rb") as f:
            retry = admin_client.post(self.upload_url(batch), {"map_files": f})

        assert retry.status_code == 200
        assert retry.json() == first.json()
        assert MapImportBatchFile.objects.filter(batch=batch).count() == 1

    def test_upload_rejects_wrong_extension(self, admin_client, tmp_path):
        batch = MapImportBatchFactory()
        bad = tmp_path / "carte.txt"
        bad.write_bytes(b"nope")

        with open(bad, "rb") as f:
            res = admin_client.post(self.upload_url(batch), {"map_files": f})

        assert res.status_code == 400
        assert MapImportBatchFile.objects.count() == 0

    def test_delete_removes_batch_file(self, admin_client):
        batch_file = MapImportBatchFileFactory()
        url = self.upload_url(batch_file.batch)

        res = admin_client.delete(f"{url}?file_id={batch_file.id}")

        assert res.status_code == 200
        assert MapImportBatchFile.objects.count() == 0

    def test_csv_form_rejects_binary_content(self, tmp_path):
        """A geopackage renamed to .csv must not pass as a csv."""
        gpkg = make_gpkg(tmp_path, "carte.gpkg")
        form = make_batch_form(SimpleUploadedFile("batch.csv", gpkg.read_bytes()))

        assert not form.is_valid()
        assert "csv_file" in form.errors

    def test_csv_form_accepts_real_csv(self):
        content = f"{CSV_HEADER}\nr1,a.gpkg,Carte A,Description A,44\n".encode()
        form = make_batch_form(SimpleUploadedFile("batch.csv", content))

        assert form.is_valid(), form.errors

    def test_upload_page_renders(self, admin_client):
        """The template wires the dropzone scripts and the already sent files."""
        batch = MapImportBatchFactory()
        MapImportBatchFileFactory(batch=batch, name="deja-envoye.gpkg")

        res = admin_client.get(self.upload_url(batch))
        content = res.content.decode()

        assert res.status_code == 200
        assert "js/libs/dropzone-upload.js" in content
        assert "js/libs/configure-batch-upload-form.js" in content
        assert "deja-envoye.gpkg" in content

    def test_view_requires_authentication(self, client):
        batch = MapImportBatchFactory()
        res = client.get(self.upload_url(batch))
        assert res.status_code == 302

    @staticmethod
    def process_url(batch):
        return reverse("admin:geodata_mapimportbatch_process", args=[batch.pk])

    def test_change_page_shows_process_button(self, admin_client):
        batch = MapImportBatchFactory()
        url = reverse("admin:geodata_mapimportbatch_change", args=[batch.pk])

        res = admin_client.get(url)

        assert res.status_code == 200
        assert self.process_url(batch) in res.content.decode()

    def test_process_queues_task(self, admin_client):
        batch = MapImportBatchFactory()
        MapImportBatchFileFactory(batch=batch)

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            res = admin_client.post(self.process_url(batch))

        assert res.status_code == 302
        mock_delay.assert_called_once_with(batch.id, only_failed=False)

    def test_process_queues_file_less_batch(self, admin_client):
        """A batch without files is a legitimate metadata-only update."""
        batch = MapImportBatchFactory()

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            admin_client.post(self.process_url(batch))

        mock_delay.assert_called_once_with(batch.id, only_failed=False)

    def test_process_retries_only_failed_lines_of_partial_batch(self, admin_client):
        batch = MapImportBatchFactory(import_status=STATUSES.partial_success)
        batch.lines.create(line_number=2, status=LINE_STATUSES.failure)

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            admin_client.post(self.process_url(batch), {"mode": "failed"})

        mock_delay.assert_called_once_with(batch.id, only_failed=True)

    def test_process_refuses_failed_retry_on_unprocessed_batch(self, admin_client):
        batch = MapImportBatchFactory(import_status=None)

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            res = admin_client.post(self.process_url(batch), {"mode": "failed"})

        assert res.status_code == 302
        mock_delay.assert_not_called()

    def test_change_page_offers_retry_only_on_partial_batch(self, admin_client):
        batch = MapImportBatchFactory(import_status=STATUSES.partial_success)
        batch.lines.create(line_number=2, status=LINE_STATUSES.failure)
        url = reverse("admin:geodata_mapimportbatch_change", args=[batch.pk])

        content = admin_client.get(url).content.decode()

        assert "Relancer les lignes en échec" in content
        assert "Relancer tout le lot" in content
        assert "Traiter le lot" not in content
        assert "(ligne 2) a échoué" in content

    def test_process_requires_post(self, admin_client):
        batch = MapImportBatchFactory()

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            res = admin_client.get(self.process_url(batch))

        assert res.status_code == 302
        mock_delay.assert_not_called()
