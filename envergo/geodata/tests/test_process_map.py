from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.db.models.fields.files import FieldFile
from django.urls import reverse

from envergo.geodata.models import STATUSES
from envergo.geodata.tasks import (
    on_map_failure,
    on_maps_chain_failure,
    process_map,
    process_map_signature,
    process_maps,
)
from envergo.geodata.tests.factories import MapFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake_map_file():
    """The factory maps have no stored file: skip opening it."""
    with patch.object(FieldFile, "open", MagicMock()):
        yield


@pytest.fixture
def notify_mock():
    with patch("envergo.geodata.tasks.notify") as mock:
        yield mock


def test_import_error_is_recorded_on_the_map():
    map = MapFactory(zones=None, expected_geometries=3)

    with patch("envergo.geodata.tasks.open_map_file", side_effect=ValueError("boom")):
        process_map_signature(map.id).apply()

    map.refresh_from_db()
    assert map.import_status == STATUSES.failure
    assert "boom" in map.import_error_msg
    assert map.task_id is None


def test_task_failure_callback_records_the_failure():
    """A crash outside the import itself (e.g. database down) is not silent."""
    map = MapFactory(zones=None)

    on_map_failure(None, RuntimeError("db down"), None, map.id)

    map.refresh_from_db()
    assert map.import_status == STATUSES.failure
    assert "db down" in map.import_error_msg


def test_failure_callback_leaves_the_notification_to_the_chain(notify_mock):
    map = MapFactory(zones=None)

    on_map_failure(None, RuntimeError("db down"), None, map.id)

    map.refresh_from_db()
    assert map.import_status == STATUSES.failure
    notify_mock.assert_not_called()


def test_map_without_geometry_is_notified(notify_mock):
    map = MapFactory(zones=None, expected_geometries=3)
    data_source = MagicMock()
    data_source.__getitem__.return_value.geom_type.name = "Polygon"

    with (
        patch("envergo.geodata.tasks.open_map_file", return_value=data_source),
        patch("envergo.geodata.tasks.process_zones_file"),
        patch("envergo.geodata.tasks.make_polygons_valid"),
        patch("envergo.geodata.tasks.simplify_map", return_value=None),
    ):
        process_map.apply(args=(map.id,))

    map.refresh_from_db()
    assert map.import_status == STATUSES.failure
    message, _ = notify_mock.call_args.args
    assert "Aucune géométrie importée" in message


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


def test_queued_map_has_its_failure_callback():
    """The map is failed even if its worker is killed."""
    assert process_map_signature(3).options["link_error"] == [on_map_failure.s(3)]


def test_maps_are_queued_as_a_chain():
    """Chained tasks run one at a time, whatever the worker concurrency."""
    with patch("envergo.geodata.tasks.chain") as mock_chain:
        process_maps([3, 1, 2])

    mock_chain.assert_called_once_with(
        process_map_signature(3), process_map_signature(1), process_map_signature(2)
    )
    mock_chain.return_value.apply_async.assert_called_once_with(
        link_error=on_maps_chain_failure.s([3, 1, 2])
    )


def test_broken_chain_fails_the_skipped_maps(notify_mock, settings):
    settings.CARTO_NOTIFICATION_HANDLERS = ["carto"]
    done, failed, skipped_1, skipped_2 = MapFactory.create_batch(
        4, zones=None, import_status=STATUSES.success
    )
    map_ids = [done.id, failed.id, skipped_1.id, skipped_2.id]

    on_maps_chain_failure(
        SimpleNamespace(args=[failed.id]), RuntimeError("oom"), None, map_ids
    )

    for map in (done, failed, skipped_1, skipped_2):
        map.refresh_from_db()
    assert done.import_status == STATUSES.success
    # Left to the map own error callback
    assert failed.import_status == STATUSES.success
    for map in (skipped_1, skipped_2):
        assert map.import_status == STATUSES.failure
        assert f"carte {failed.id} a échoué" in map.import_error_msg
        assert map.import_date is not None

    # A single summary notification
    notify_mock.assert_called_once()
    message, site = notify_mock.call_args.args
    assert site == "amenagement"
    assert reverse("admin:geodata_map_change", args=[failed.id]) in message
    assert "oom" in message
    assert reverse("admin:geodata_map_change", args=[skipped_1.id]) in message
    assert reverse("admin:geodata_map_change", args=[skipped_2.id]) in message
    assert reverse("admin:geodata_map_change", args=[done.id]) not in message
    assert "ping carto" in message


def test_failure_of_the_last_map_skips_nothing(notify_mock):
    done, failed = MapFactory.create_batch(
        2, zones=None, import_status=STATUSES.success
    )

    on_maps_chain_failure(
        SimpleNamespace(args=[failed.id]),
        RuntimeError("oom"),
        None,
        [done.id, failed.id],
    )

    done.refresh_from_db()
    assert done.import_status == STATUSES.success
    message, _ = notify_mock.call_args.args
    assert "non importées" not in message


def test_failed_map_stops_the_chain_and_fails_the_next_ones(notify_mock):
    failed, skipped = MapFactory.create_batch(
        2, zones=None, import_status=STATUSES.success
    )

    with patch("envergo.geodata.tasks.open_map_file", side_effect=ValueError("boom")):
        # An eager chain raises the failure when moving on to the next task
        with pytest.raises(ValueError, match="boom"):
            process_maps([failed.id, skipped.id])

    skipped.refresh_from_db()
    assert skipped.import_status == STATUSES.failure
    assert f"carte {failed.id} a échoué" in skipped.import_error_msg
    notify_mock.assert_called_once()
    message, _ = notify_mock.call_args.args
    assert "boom" in message


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
