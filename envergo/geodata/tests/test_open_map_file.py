import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.fields.files import FieldFile
from django.forms import modelform_factory

from envergo.geodata.admin import MapForm
from envergo.geodata.management.commands.batch_import_maps import (
    Command as BatchImportCommand,
)
from envergo.geodata.management.commands.batch_import_maps import ParsedRow
from envergo.geodata.models import STATUSES, Map
from envergo.geodata.tasks import process_map
from envergo.geodata.utils import InvalidMapFile, open_map_file

DATA_DIR = Path(__file__).parent / "data"


def make_upload(fixture_name):
    content = (DATA_DIR / fixture_name).read_bytes()
    return SimpleUploadedFile(fixture_name, content)


def make_stored_file(fixture_name):
    """A map file saved to the default storage."""
    field = Map._meta.get_field("file")
    with open(DATA_DIR / fixture_name, "rb") as fixture:
        name = field.storage.save(f"maps/{fixture_name}", File(fixture))
    return FieldFile(None, field, name)


def test_geopackage_opens():
    with open_map_file(make_upload("zones.gpkg")) as data_source:
        layer = data_source[0]
        assert len(layer) == 2
        assert layer.geom_type.name == "Polygon"


def test_zipped_shapefile_opens():
    with open_map_file(make_upload("lines.zip")) as data_source:
        layer = data_source[0]
        assert len(layer) == 2
        assert layer.geom_type.name == "LineString"


def test_stored_file_copy_is_deleted_on_exit():
    with open_map_file(make_stored_file("zones.gpkg")) as data_source:
        local_copy = Path(data_source.name)
        assert local_copy.suffix == ".gpkg"
    assert not local_copy.exists()


def test_unsupported_format_is_rejected_before_reading():
    file = Mock(spec=["name", "seek", "read"])
    file.name = "map.csv"
    with pytest.raises(InvalidMapFile):
        with open_map_file(file):
            pass
    file.read.assert_not_called()


@pytest.mark.parametrize("fixture_name", ["corrupt.gpkg", "no_shapefile.zip"])
def test_unreadable_map_is_rejected(fixture_name):
    with pytest.raises(InvalidMapFile):
        with open_map_file(make_upload(fixture_name)):
            pass


@pytest.mark.django_db
@pytest.mark.parametrize("fixture_name", ["zones.gpkg", "lines.zip"])
def test_process_map_imports_every_geometry(fixture_name):
    map = Map.objects.create(name="Test", description="Test", expected_geometries=2)
    with open(DATA_DIR / fixture_name, "rb") as fixture:
        map.file.save(fixture_name, File(fixture))

    process_map.delay(map.id)

    map.refresh_from_db()
    assert map.import_error_msg == ""
    assert map.import_status == STATUSES.success
    assert map.imported_geometries == 2


@pytest.mark.django_db
@patch.object(FieldFile, "close", autospec=True)
def test_process_map_closes_the_stored_file(mock_close):
    map = Map.objects.create(name="Test", description="Test")
    with open(DATA_DIR / "zones.gpkg", "rb") as fixture:
        map.file.save("zones.gpkg", File(fixture))

    process_map.delay(map.id)

    mock_close.assert_called_once()


def make_map_form(upload, instance=None):
    form_class = modelform_factory(
        Map, form=MapForm, fields=["name", "description", "file"]
    )
    data = {"name": "Test", "description": "Test"}
    files = {"file": upload} if upload else {}
    return form_class(data, files, instance=instance)


@pytest.mark.django_db
def test_map_form_counts_features_of_new_upload():
    form = make_map_form(make_upload("zones.gpkg"))
    assert form.is_valid()
    assert form.instance.expected_geometries == 2


@pytest.mark.django_db
def test_map_form_rejects_unreadable_upload():
    form = make_map_form(make_upload("corrupt.gpkg"))
    assert not form.is_valid()
    assert "file" in form.errors


@pytest.mark.django_db
@patch("envergo.geodata.admin.open_map_file")
def test_map_form_skips_unchanged_file(mock_open_map_file):
    map = Map.objects.create(name="Test", description="Test", expected_geometries=2)
    with open(DATA_DIR / "zones.gpkg", "rb") as fixture:
        map.file.save("zones.gpkg", File(fixture))

    form = make_map_form(None, instance=map)
    assert form.is_valid()
    mock_open_map_file.assert_not_called()


@pytest.mark.django_db
def test_batch_import_counts_features(tmp_path):
    shutil.copy(DATA_DIR / "zones.gpkg", tmp_path / "zones.gpkg")
    row = ParsedRow(
        file="zones.gpkg",
        name="Test",
        display_name="Test",
        description="Test",
        source="",
        map_type="",
        data_type="certain",
    )

    BatchImportCommand().import_row(row, tmp_path)

    map = Map.objects.get(name="Test")
    assert map.expected_geometries == 2
    assert map.file.read() == (DATA_DIR / "zones.gpkg").read_bytes()
