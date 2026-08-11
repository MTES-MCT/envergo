import shutil
import sqlite3
import zipfile
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import modelform_factory
from django.urls import reverse

from envergo.geodata.admin import MapImportBatchForm
from envergo.geodata.import_batch import parse_batch_row, validate_headers
from envergo.geodata.models import STATUSES, Map, MapImportBatch, MapImportBatchFile
from envergo.geodata.tasks import process_map_import_batch
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
    try:
        shutil.copy(GPKG_TEMPLATE, path)
    except FileNotFoundError:
        # Fall back to a minimal sqlite database
        con = sqlite3.connect(path)
        con.execute("create table gpkg_contents (table_name text)")
        con.commit()
        con.close()
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


def run_task(batch):
    with (
        patch("envergo.geodata.tasks.count_features", return_value=42),
        patch("envergo.geodata.tasks.process_map.delay") as mock_delay,
    ):
        process_map_import_batch.apply(args=(batch.id,))
    batch.refresh_from_db()
    return mock_delay


def test_validate_headers_reports_missing_columns():
    errors = validate_headers(["reference", "file"])
    assert len(errors) == 1
    assert "name" in errors[0]
    assert "description" in errors[0]
    assert "departments" in errors[0]

    assert validate_headers(CSV_HEADER.split(",")) == []
    assert validate_headers(None)


def test_parse_batch_row_requires_reference_file_and_name():
    row = {"reference": "", "file": "a.gpkg", "name": "N", "description": ""}
    _, errors = parse_batch_row(2, row)
    assert "référence manquante" in errors[0]

    row = {"reference": "r1", "file": " ", "name": "N", "description": ""}
    _, errors = parse_batch_row(2, row)
    assert "fichier manquant" in errors[0]

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
    mock_delay = run_task(batch)

    assert batch.import_status == STATUSES.failure
    assert "Colonnes manquantes" in batch.import_log
    assert Map.objects.count() == 0
    assert mock_delay.call_count == 0


def test_batch_creates_maps():
    csv_content = (
        f"{CSV_HEADER},map_type\n"
        'r1,a.gpkg,Carte A,Description A,"44,56",zone_humide\n'
        "r2,b.gpkg,Carte B,Description B,29,zone_inondable\n"
    )
    batch = make_batch(csv_content, filenames=["a.gpkg", "b.gpkg"])
    mock_delay = run_task(batch)

    assert batch.import_status == STATUSES.success
    assert batch.import_log == ""

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
    assert mock_delay.call_count == 2


def test_batch_updates_existing_map():
    existing = MapFactory(
        reference="r1",
        name="Ancien nom",
        display_name="Nom d'affichage",
        batch_created_at=None,
    )
    csv_content = f"{CSV_HEADER}\nr1,a.gpkg,Nouveau nom,Nouvelle description,44\n"
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    mock_delay = run_task(batch)

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
    assert mock_delay.call_count == 1


def test_batch_isolates_row_errors():
    csv_content = (
        f"{CSV_HEADER},map_type\n"
        "r1,a.gpkg,Carte A,Description A,44,nope\n"
        "r2,missing.gpkg,Carte B,Description B,29,\n"
        "r3,c.gpkg,Carte C,Description C,29,\n"
    )
    batch = make_batch(csv_content, filenames=["a.gpkg", "c.gpkg"])
    mock_delay = run_task(batch)

    assert batch.import_status == STATUSES.partial_success
    assert "ligne 2" in batch.import_log
    assert "map_type inconnu" in batch.import_log
    assert "ligne 3" in batch.import_log
    assert "absent des fichiers téléversés" in batch.import_log
    assert Map.objects.count() == 1
    assert Map.objects.filter(reference="r3").exists()
    assert mock_delay.call_count == 1


def test_batch_skips_duplicate_references():
    csv_content = (
        f"{CSV_HEADER}\n"
        "r1,a.gpkg,Carte A,Description A,44\n"
        "r1,b.gpkg,Carte A bis,Description bis,56\n"
    )
    batch = make_batch(csv_content, filenames=["a.gpkg", "b.gpkg"])
    run_task(batch)

    assert batch.import_status == STATUSES.partial_success
    assert "en double" in batch.import_log
    assert Map.objects.count() == 1
    assert Map.objects.get(reference="r1").name == "Carte A"


def test_batch_with_only_errors_fails():
    csv_content = f"{CSV_HEADER}\nr1,missing.gpkg,Carte A,Description A,44\n"
    batch = make_batch(csv_content)
    mock_delay = run_task(batch)

    assert batch.import_status == STATUSES.failure
    assert Map.objects.count() == 0
    assert mock_delay.call_count == 0


def test_batch_blank_rows_are_skipped():
    csv_content = f"{CSV_HEADER}\nr1,a.gpkg,Carte A,Description A,44\n,,,,\n"
    batch = make_batch(csv_content, filenames=["a.gpkg"])
    run_task(batch)

    assert batch.import_status == STATUSES.success
    assert Map.objects.count() == 1


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

    def test_view_requires_authentication(self, client):
        batch = MapImportBatchFactory()
        res = client.get(self.upload_url(batch))
        assert res.status_code == 302

    def test_process_action_queues_task(self, admin_client):
        batch = MapImportBatchFactory()
        MapImportBatchFileFactory(batch=batch)
        url = reverse("admin:geodata_mapimportbatch_changelist")

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            res = admin_client.post(
                url,
                {"action": "process", "_selected_action": [batch.pk]},
            )

        assert res.status_code == 302
        mock_delay.assert_called_once_with(batch.id)

    def test_process_action_refuses_empty_batch(self, admin_client):
        batch = MapImportBatchFactory()
        url = reverse("admin:geodata_mapimportbatch_changelist")

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            admin_client.post(
                url,
                {"action": "process", "_selected_action": [batch.pk]},
            )

        assert mock_delay.call_count == 0

    def test_process_action_queues_several_batches(self, admin_client):
        batches = [MapImportBatchFactory(name=f"Lot {i}") for i in range(3)]
        for batch in batches:
            MapImportBatchFileFactory(batch=batch)
        url = reverse("admin:geodata_mapimportbatch_changelist")

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            res = admin_client.post(
                url,
                {"action": "process", "_selected_action": [b.pk for b in batches]},
            )

        assert res.status_code == 302
        assert mock_delay.call_count == 3
        assert {c.args[0] for c in mock_delay.call_args_list} == {b.id for b in batches}

    def test_process_action_skips_only_the_empty_batch(self, admin_client):
        """One misconfigured batch must not cancel the others."""
        full = MapImportBatchFactory(name="Lot complet")
        MapImportBatchFileFactory(batch=full)
        empty = MapImportBatchFactory(name="Lot vide")
        url = reverse("admin:geodata_mapimportbatch_changelist")

        with patch(
            "envergo.geodata.admin.process_map_import_batch.delay"
        ) as mock_delay:
            admin_client.post(
                url,
                {"action": "process", "_selected_action": [full.pk, empty.pk]},
            )

        mock_delay.assert_called_once_with(full.id)
