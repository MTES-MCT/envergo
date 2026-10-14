from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.db.models.fields.files import FieldFile
from django.urls import reverse
from django.utils import timezone

from envergo.geodata.models import STATUSES, Map
from envergo.geodata.tasks import process_map
from envergo.geodata.tests.factories import MapFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake_map_file():
    """The factory maps have no stored file: skip opening it."""
    with patch.object(FieldFile, "open", MagicMock()):
        yield


def _stalled_map(**kwargs):
    return MapFactory(
        zones=None,
        import_status=None,
        task_id="abc",
        import_date=timezone.now() - timedelta(hours=1),
        **kwargs,
    )


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


def test_retry_restarts_the_stalled_delay():
    map = _stalled_map()

    process_map.on_retry(RuntimeError("db down"), "tid", (map.id,), {}, None)

    map.refresh_from_db()
    assert not map.is_import_stalled


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


def test_stalled_queryset_and_property():
    stalled = _stalled_map()
    running = MapFactory(
        zones=None, import_status=None, task_id="abc", import_date=timezone.now()
    )
    pending = MapFactory(zones=None, import_status=None)
    done = MapFactory(
        zones=None,
        import_status=STATUSES.success,
        task_id=None,
        import_date=timezone.now() - timedelta(hours=1),
    )

    assert list(Map.objects.stalled()) == [stalled]
    assert stalled.is_import_stalled
    assert not any(m.is_import_stalled for m in (running, pending, done))


def test_admin_filter_lists_stalled_maps(admin_client):
    stalled = _stalled_map(name="stalled")
    MapFactory(zones=None, name="fine", import_status=STATUSES.success)

    url = reverse("admin:geodata_map_changelist")
    response = admin_client.get(url, {"stalled_import": "1"})

    assert response.status_code == 200
    assert [m.pk for m in response.context["cl"].result_list] == [stalled.pk]
