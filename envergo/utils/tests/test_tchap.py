import asyncio
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from django.core.cache import cache
from nio import RoomSendError, SyncError

from envergo.utils import tchap


@pytest.fixture(autouse=True)
def tchap_settings(settings):
    """Configure a fake but "present" Tchap setup for every test in this file."""
    settings.TCHAP_HOMESERVER_URL = "https://tchap.example.org"
    settings.TCHAP_USER_ID = "@bot:example.org"
    settings.TCHAP_ACCESS_TOKEN = "fake-token"
    settings.TCHAP_DEVICE_ID = "envergo-test"
    settings.TCHAP_ROOM_ID_AMENAGEMENT = "!amenagement:example.org"
    settings.TCHAP_ROOM_ID_HAIE = "!haie:example.org"
    cache.delete(tchap.LOCK_KEY)
    yield
    cache.delete(tchap.LOCK_KEY)


def _fake_storage(existing_bytes=None):
    """A storages["tchap"]-shaped mock, with or without a pre-existing blob."""
    storage = MagicMock()
    storage.exists.return_value = existing_bytes is not None
    if existing_bytes is not None:
        storage.open.return_value.__enter__.return_value.read.return_value = (
            existing_bytes
        )
    return storage


def _mock_nio_client(**overrides):
    client = MagicMock()
    client.loaded_sync_token = overrides.get("loaded_sync_token", "")
    client.should_upload_keys = overrides.get("should_upload_keys", False)
    client.rooms = overrides.get("rooms", {})
    client.sync = AsyncMock(return_value=overrides.get("sync_return", MagicMock()))
    client.keys_upload = AsyncMock()
    client.room_send = AsyncMock(
        return_value=overrides.get("room_send_return", MagicMock())
    )
    client.close = AsyncMock()
    return client


# ---- notify() ---------------------------------------------------------


def test_notify_not_configured_falls_back_to_mattermost(settings):
    settings.TCHAP_ACCESS_TOKEN = None
    with (
        patch("envergo.utils.tchap._notify_with_lock") as mock_lock,
        patch("envergo.utils.mattermost.notify") as mock_mattermost,
    ):
        tchap.notify("hello", "amenagement")
    mock_lock.assert_not_called()
    mock_mattermost.assert_called_once_with("hello", "amenagement")


@pytest.mark.parametrize(
    "site, room_setting",
    [("haie", "TCHAP_ROOM_ID_HAIE"), ("amenagement", "TCHAP_ROOM_ID_AMENAGEMENT")],
)
def test_notify_picks_room_by_site(settings, site, room_setting):
    with (
        patch("envergo.utils.tchap._notify_with_lock") as mock_lock,
        patch("envergo.utils.mattermost.notify"),
    ):
        tchap.notify("hello", site)
    mock_lock.assert_called_once_with("hello", getattr(settings, room_setting))


def test_notify_swallows_tchap_failure_and_still_calls_mattermost():
    with (
        patch("envergo.utils.tchap._notify_with_lock", side_effect=Exception("boom")),
        patch("envergo.utils.mattermost.notify") as mock_mattermost,
    ):
        tchap.notify("hello", "amenagement")
    mock_mattermost.assert_called_once_with("hello", "amenagement")


# ---- locking ------------------------------------------------------------


def test_acquire_lock_succeeds_when_free():
    assert tchap._acquire_lock("token-a") is True
    assert cache.get(tchap.LOCK_KEY) == "token-a"


def test_acquire_lock_fails_when_held():
    with (
        patch("envergo.utils.tchap.cache.add", return_value=False) as mock_add,
        patch("envergo.utils.tchap.time.sleep") as mock_sleep,
    ):
        assert tchap._acquire_lock("token-a") is False
    assert mock_add.call_count == tchap.LOCK_ACQUIRE_RETRIES
    assert mock_sleep.call_count == tchap.LOCK_ACQUIRE_RETRIES


def test_acquire_lock_retries_then_succeeds():
    with (
        patch("envergo.utils.tchap.cache.add", side_effect=[False, True]) as mock_add,
        patch("envergo.utils.tchap.time.sleep") as mock_sleep,
    ):
        assert tchap._acquire_lock("token-a") is True
    assert mock_add.call_count == 2
    mock_sleep.assert_called_once()


def test_release_lock_ignores_a_lock_it_does_not_own():
    cache.set(tchap.LOCK_KEY, "someone-else", timeout=30)
    tchap._release_lock("token-a")
    assert cache.get(tchap.LOCK_KEY) == "someone-else"


def test_release_lock_deletes_its_own_lock():
    cache.set(tchap.LOCK_KEY, "token-a", timeout=30)
    tchap._release_lock("token-a")
    assert cache.get(tchap.LOCK_KEY) is None


def test_notify_with_lock_calls_store_and_releases():
    with patch("envergo.utils.tchap._notify_with_store") as mock_store:
        tchap._notify_with_lock("hello", "!room:example.org")
    mock_store.assert_called_once_with("hello", "!room:example.org")
    assert cache.get(tchap.LOCK_KEY) is None


def test_notify_with_lock_releases_even_on_failure():
    with patch("envergo.utils.tchap._notify_with_store", side_effect=Exception("boom")):
        with pytest.raises(Exception):
            tchap._notify_with_lock("hello", "!room:example.org")
    assert cache.get(tchap.LOCK_KEY) is None


def test_notify_with_lock_skips_store_when_lock_unavailable():
    with (
        patch("envergo.utils.tchap._acquire_lock", return_value=False),
        patch("envergo.utils.tchap._notify_with_store") as mock_store,
    ):
        tchap._notify_with_lock("hello", "!room:example.org")
    mock_store.assert_not_called()


# ---- _notify_with_store (checkpoint) -------------------------------------


def test_notify_with_store_downloads_existing_blob_before_send(settings):
    storage = _fake_storage(existing_bytes=b"previous-state")
    db_name = f"{settings.TCHAP_USER_ID}_{settings.TCHAP_DEVICE_ID}.db"
    seen = {}

    async def fake_send(msg, room_id, store_path):
        seen["content"] = (Path(store_path) / db_name).read_bytes()

    with (
        patch("envergo.utils.tchap.storages", {"tchap": storage}),
        patch("envergo.utils.tchap._send", side_effect=fake_send),
    ):
        tchap._notify_with_store("hello", "!room:example.org")

    assert seen["content"] == b"previous-state"


def test_notify_with_store_skips_download_when_no_existing_blob(settings):
    storage = _fake_storage(existing_bytes=None)
    db_name = f"{settings.TCHAP_USER_ID}_{settings.TCHAP_DEVICE_ID}.db"
    seen = {}

    async def fake_send(msg, room_id, store_path):
        seen["exists"] = (Path(store_path) / db_name).exists()

    with (
        patch("envergo.utils.tchap.storages", {"tchap": storage}),
        patch("envergo.utils.tchap._send", side_effect=fake_send),
    ):
        tchap._notify_with_store("hello", "!room:example.org")

    assert seen["exists"] is False
    storage.open.assert_not_called()


def test_notify_with_store_uploads_state_after_successful_send(settings):
    storage = _fake_storage()
    db_name = f"{settings.TCHAP_USER_ID}_{settings.TCHAP_DEVICE_ID}.db"

    async def fake_send(msg, room_id, store_path):
        (Path(store_path) / db_name).write_bytes(b"new-state")

    with (
        patch("envergo.utils.tchap.storages", {"tchap": storage}),
        patch("envergo.utils.tchap._send", side_effect=fake_send),
    ):
        tchap._notify_with_store("hello", "!room:example.org")

    saved_name, saved_content = storage.save.call_args[0]
    assert saved_name == db_name
    assert saved_content.read() == b"new-state"


def test_notify_with_store_uploads_state_even_if_send_fails(settings):
    """A failed send must not lose local state nio already wrote to disk."""
    storage = _fake_storage()
    db_name = f"{settings.TCHAP_USER_ID}_{settings.TCHAP_DEVICE_ID}.db"

    async def fake_send(msg, room_id, store_path):
        (Path(store_path) / db_name).write_bytes(b"partial-state")
        raise Exception("boom")

    with (
        patch("envergo.utils.tchap.storages", {"tchap": storage}),
        patch("envergo.utils.tchap._send", side_effect=fake_send),
    ):
        tchap._notify_with_store("hello", "!room:example.org")  # must not raise

    saved_name, saved_content = storage.save.call_args[0]
    assert saved_content.read() == b"partial-state"


def test_notify_with_store_skips_upload_if_nio_never_wrote_anything(settings):
    storage = _fake_storage()

    async def fake_send(msg, room_id, store_path):
        raise Exception("boom before nio touched the store")

    with (
        patch("envergo.utils.tchap.storages", {"tchap": storage}),
        patch("envergo.utils.tchap._send", side_effect=fake_send),
    ):
        tchap._notify_with_store("hello", "!room:example.org")

    storage.save.assert_not_called()


# ---- _send() (nio mocked, no network) -------------------------------------


def test_send_happy_path(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(rooms={room_id: MagicMock()})

    with patch("envergo.utils.tchap.AsyncClient", return_value=client) as mock_cls:
        asyncio.run(tchap._send("**hello**", room_id, str(tmp_path)))

    mock_cls.assert_called_once_with(
        homeserver=settings.TCHAP_HOMESERVER_URL,
        user=settings.TCHAP_USER_ID,
        device_id=settings.TCHAP_DEVICE_ID,
        store_path=str(tmp_path),
        config=ANY,
    )
    client.restore_login.assert_called_once_with(
        user_id=settings.TCHAP_USER_ID,
        device_id=settings.TCHAP_DEVICE_ID,
        access_token=settings.TCHAP_ACCESS_TOKEN,
    )
    client.keys_upload.assert_not_called()
    _, kwargs = client.room_send.call_args
    assert kwargs["room_id"] == room_id
    assert kwargs["message_type"] == "m.room.message"
    assert kwargs["ignore_unverified_devices"] is True
    assert kwargs["content"] == {
        "msgtype": "m.text",
        "body": "**hello**",
        "format": "org.matrix.custom.html",
        "formatted_body": "<p><strong>hello</strong></p>",
    }
    client.close.assert_called_once()


def test_send_uploads_keys_when_needed(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(should_upload_keys=True, rooms={room_id: MagicMock()})

    with patch("envergo.utils.tchap.AsyncClient", return_value=client):
        asyncio.run(tchap._send("hello", room_id, str(tmp_path)))

    client.keys_upload.assert_called_once()


def test_send_returns_early_on_sync_error(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(sync_return=SyncError("boom"))

    with patch("envergo.utils.tchap.AsyncClient", return_value=client):
        asyncio.run(tchap._send("hello", room_id, str(tmp_path)))

    client.room_send.assert_not_called()
    client.close.assert_called_once()


def test_send_returns_early_when_room_not_joined(settings, tmp_path):
    client = _mock_nio_client(rooms={})

    with patch("envergo.utils.tchap.AsyncClient", return_value=client):
        asyncio.run(
            tchap._send("hello", settings.TCHAP_ROOM_ID_AMENAGEMENT, str(tmp_path))
        )

    client.room_send.assert_not_called()
    client.close.assert_called_once()


def test_send_logs_room_send_error_without_raising(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(
        rooms={room_id: MagicMock()}, room_send_return=RoomSendError("boom")
    )

    with patch("envergo.utils.tchap.AsyncClient", return_value=client):
        asyncio.run(tchap._send("hello", room_id, str(tmp_path)))  # must not raise

    client.close.assert_called_once()


def test_send_closes_client_even_if_sync_raises(settings, tmp_path):
    client = _mock_nio_client()
    client.sync = AsyncMock(side_effect=RuntimeError("network exploded"))

    with patch("envergo.utils.tchap.AsyncClient", return_value=client):
        with pytest.raises(RuntimeError):
            asyncio.run(
                tchap._send("hello", settings.TCHAP_ROOM_ID_AMENAGEMENT, str(tmp_path))
            )

    client.close.assert_called_once()
