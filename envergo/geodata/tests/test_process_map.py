from unittest.mock import MagicMock, patch

import pytest
from django.db.models.fields.files import FieldFile

from envergo.geodata.models import STATUSES
from envergo.geodata.tasks import process_map, process_maps
from envergo.geodata.tests.factories import MapFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake_map_file():
    """The factory maps have no stored file: skip opening it."""
    with patch.object(FieldFile, "open", MagicMock()):
        yield


def test_import_error_is_recorded_on_the_map():
    map = MapFactory(zones=None, expected_geometries=3)

    with patch("envergo.geodata.tasks.open_map_file", side_effect=ValueError("boom")):
        process_map.apply(args=(map.id,))

    map.refresh_from_db()
    assert map.import_status == STATUSES.failure
    assert "boom" in map.import_error_msg
    assert map.task_id is None


def test_task_failure_hook_records_the_failure():
    """A crash outside the import itself (e.g. database down) is not silent."""
    map = MapFactory(zones=None)

    process_map.on_failure(RuntimeError("db down"), "tid", (map.id,), {}, None)

    map.refresh_from_db()
    assert map.import_status == STATUSES.failure
    assert "db down" in map.import_error_msg


def test_started_task_leaves_a_trace():
    """The started state is committed, not rolled back with a dying task."""
    map = MapFactory(zones=None)

    # BaseException is not caught by the import error handling
    with patch("envergo.geodata.tasks.open_map_file", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            process_map.apply(args=(map.id,), throw=True)

    map.refresh_from_db()
    assert map.import_status is None
    assert map.task_id is not None
    assert map.import_date is not None


def test_maps_are_queued_as_a_chain():
    """Chained tasks run one at a time, whatever the worker concurrency."""
    with patch("envergo.geodata.tasks.chain") as mock_chain:
        process_maps([3, 1, 2])

    signatures = mock_chain.call_args.args
    assert [sig.args for sig in signatures] == [(3,), (1,), (2,)]
    mock_chain.return_value.delay.assert_called_once_with()


def test_nothing_is_queued_without_maps():
    with patch("envergo.geodata.tasks.chain") as mock_chain:
        process_maps([])

    mock_chain.assert_not_called()


def test_import_stops_once_the_transaction_is_broken():
    """A swallowed save error must not let the loop run on every feature."""
    from django.db import connection, transaction

    from envergo.geodata.models import Zone
    from envergo.geodata.tests.test_open_map_file import DATA_DIR
    from envergo.geodata.utils import open_map_file, process_zones_file

    map = MapFactory(zones=None)
    calls = []

    def break_transaction(zone, *args, **kwargs):
        calls.append(zone)
        connection.set_rollback(True)
        raise RuntimeError("timeout")

    with open(DATA_DIR / "zones.gpkg", "rb") as source:
        with open_map_file(source) as data_source:
            with transaction.atomic(), patch.object(Zone, "save", break_transaction):
                with pytest.raises(RuntimeError, match="Import interrompu.*timeout"):
                    process_zones_file(map, data_source)
                assert len(calls) == 1
                connection.set_rollback(False)
