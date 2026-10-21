import shutil
import zipfile
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import modelform_factory
from django.urls import reverse

from envergo.geodata.admin import MapImportBatchForm
from envergo.geodata.import_batch import parse_batch_row, validate_headers
from envergo.geodata.models import STATUSES, Map, MapImportBatch, MapImportBatchFile
from envergo.geodata.tasks import (
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


def run_task(batch):
    """Run the whole batch chain eagerly and return the ids of processed maps.

    `process_map` is stubbed: its geometry import is tested on its own.
    """
    processed = []
    with (
        patch("envergo.geodata.tasks.open_map_file", fake_open_map_file),
        patch.object(process_map, "run", side_effect=processed.append),
    ):
        process_map_import_batch.apply(args=(batch.id,))
    batch.refresh_from_db()
    return processed


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
    assert "description manquante" in batch.import_log
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
    assert "Colonnes manquantes" in batch.import_log
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
    assert batch.import_log == "Résumé : 2/2 ligne(s) importée(s)."

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
    assert "fichier manquant pour une carte inexistante" in batch.import_log
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
    lines = batch.import_log.splitlines()
    assert lines[0] == "Résumé : aucune ligne importée, csv non valide."
    assert len(lines) == 4
    assert "Ligne 2 : map_type inconnu" in lines[1]
    assert "Ligne 4 : fichier référencé non téléversé : missing.gpkg" in lines[2]
    assert "Ligne 5 : référence en double" in lines[3]
    assert Map.objects.count() == 0
    assert processed == []


def test_batch_blank_rows_are_skipped():
    csv_content = f"{CSV_HEADER}\nr1,a.gpkg,Carte A,Description A,44\n,,,,\n"
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    run_task(batch)

    assert batch.import_status == STATUSES.success
    assert Map.objects.count() == 1


def test_import_batch_row_collects_errors_and_skips_the_row():
    """A row failing validation is reported to the next task, not imported."""
    batch = make_batch(f"{CSV_HEADER}\n")
    raw_row = {
        "reference": "r1",
        "file": "missing.gpkg",
        "name": "Carte A",
        "description": "Description A",
        "departments": "44",
    }

    result = import_batch_row.apply(args=(None, batch.id, 0, 2, raw_row)).get()

    assert list(result) == [0]
    assert "missing.gpkg" in result[0][0]
    assert Map.objects.count() == 0

    # The dict built by the previous rows is completed, not replaced.
    result = import_batch_row.apply(
        args=({"3": ["avant"]}, batch.id, 1, 3, raw_row)
    ).get()
    assert set(result) == {"3", 1}


def test_finalize_batch_reports_failed_rows():
    batch = make_batch(f"{CSV_HEADER}\n")
    # Keys are strings once the dict went through the json serializer.
    errors_by_line = {"2": ["ligne 5 : a", "ligne 5 : b"], "0": ["ligne 2 : c"]}

    finalize_batch.apply(args=(errors_by_line, batch.id, 4))
    batch.refresh_from_db()

    assert batch.import_status == STATUSES.partial_success
    assert batch.import_log.splitlines() == [
        "Résumé : 2/4 ligne(s) importée(s).",
        "L'import 1/4 a échoué : ligne 2 : c",
        "L'import 3/4 a échoué : ligne 5 : a ; ligne 5 : b",
    ]
    assert batch.task_id is None
    assert batch.import_date is not None


@pytest.mark.parametrize(
    "errors_by_line,expected",
    [
        (None, STATUSES.success),
        ({}, STATUSES.success),
        ({"0": ["e"]}, STATUSES.partial_success),
        ({"0": ["e"], "1": ["e"]}, STATUSES.failure),
    ],
)
def test_finalize_batch_status(errors_by_line, expected):
    batch = make_batch(f"{CSV_HEADER}\n")

    finalize_batch.apply(args=(errors_by_line, batch.id, 2))
    batch.refresh_from_db()

    assert batch.import_status == expected


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
        mock_delay.assert_called_once_with(batch.id)

    def test_process_queues_file_less_batch(self, admin_client):
        """A batch without files is a legitimate metadata-only update."""
        batch = MapImportBatchFactory()

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            admin_client.post(self.process_url(batch))

        mock_delay.assert_called_once_with(batch.id)

    def test_process_requires_post(self, admin_client):
        batch = MapImportBatchFactory()

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            res = admin_client.get(self.process_url(batch))

        assert res.status_code == 302
        mock_delay.assert_not_called()
