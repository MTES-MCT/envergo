import asyncio
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from django.core.cache import cache
from nio import JoinError, RoomSendError, SyncError

from envergo.tchap import notifications
from envergo.tchap.models import TchapCredential
from envergo.utils import mattermost

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def tchap_settings(settings):
    """Configure a fake but "present" Tchap setup for every test in this file."""
    settings.TCHAP_HOMESERVER_URL = "https://notifications.example.org"
    settings.TCHAP_USER_ID = "@bot:example.org"
    settings.TCHAP_ROOM_ID_AMENAGEMENT = "!amenagement:example.org"
    settings.TCHAP_ROOM_ID_HAIE = "!haie:example.org"
    cache.delete(notifications.LOCK_KEY)
    yield
    cache.delete(notifications.LOCK_KEY)


def _mock_nio_client(**overrides):
    client = MagicMock()
    client.loaded_sync_token = overrides.get("loaded_sync_token", "")
    client.should_upload_keys = overrides.get("should_upload_keys", False)
    client.rooms = overrides.get("rooms", {})
    client.invited_rooms = overrides.get("invited_rooms", {})
    client.sync = AsyncMock(return_value=overrides.get("sync_return", MagicMock()))
    client.keys_upload = AsyncMock()
    client.join = AsyncMock(return_value=overrides.get("join_return", MagicMock()))
    client.room_send = AsyncMock(
        return_value=overrides.get("room_send_return", MagicMock())
    )
    client.close = AsyncMock()
    return client


CREDS = TchapCredential(
    user_id="@bot:example.org", device_id="envergo-test", access_token="fake-token"
)


def _make_credentials(crypto_store=None):
    """Persist and return the single credentials row the send path fetches."""
    return TchapCredential.objects.create(
        user_id=CREDS.user_id,
        device_id=CREDS.device_id,
        access_token=CREDS.access_token,
        crypto_store=crypto_store,
    )


# ---- get_credentials() --------------------------------------------------


def test_get_credentials_returns_none_when_no_row():
    assert notifications.get_credentials() is None


def test_get_credentials_returns_the_row():
    row = TchapCredential.objects.create(
        user_id="@bot:db.example.org",
        device_id="DBDEVICE",
        access_token="db-token",
    )
    creds = notifications.get_credentials()
    assert creds.pk == row.pk
    assert (creds.user_id, creds.device_id, creds.access_token) == (
        "@bot:db.example.org",
        "DBDEVICE",
        "db-token",
    )


# ---- deliver() --------------------------------------------------------


def test_deliver_without_a_room_falls_back_to_mattermost(settings):
    """No room configured for the site: don't even reach for the lock."""
    settings.TCHAP_ROOM_ID_AMENAGEMENT = None
    with (
        patch("envergo.tchap.notifications._notify_with_lock") as mock_lock,
        patch("envergo.utils.mattermost.notify") as mock_mattermost,
    ):
        notifications.deliver("hello", "amenagement")
    mock_lock.assert_not_called()
    mock_mattermost.assert_called_once_with("hello", "amenagement")


@pytest.mark.parametrize(
    "site, room_setting",
    [("haie", "TCHAP_ROOM_ID_HAIE"), ("amenagement", "TCHAP_ROOM_ID_AMENAGEMENT")],
)
def test_deliver_picks_room_by_site(settings, site, room_setting):
    _make_credentials()
    with (
        patch("envergo.tchap.notifications._notify_with_lock") as mock_lock,
        patch("envergo.utils.mattermost.notify"),
    ):
        notifications.deliver("hello", site)
    mock_lock.assert_called_once_with("hello", getattr(settings, room_setting))


def test_deliver_swallows_tchap_failure_and_still_calls_mattermost():
    _make_credentials()
    with (
        patch(
            "envergo.tchap.notifications._notify_with_lock",
            side_effect=Exception("boom"),
        ),
        patch("envergo.utils.mattermost.notify") as mock_mattermost,
    ):
        notifications.deliver("hello", "amenagement")
    mock_mattermost.assert_called_once_with("hello", "amenagement")


# ---- locking ------------------------------------------------------------


def test_acquire_lock_succeeds_when_free():
    assert notifications._acquire_lock("token-a") is True
    assert cache.get(notifications.LOCK_KEY) == "token-a"


def test_acquire_lock_fails_when_held():
    with (
        patch("envergo.tchap.notifications.cache.add", return_value=False) as mock_add,
        patch("envergo.tchap.notifications.time.sleep") as mock_sleep,
    ):
        assert notifications._acquire_lock("token-a") is False
    assert mock_add.call_count == notifications.LOCK_ACQUIRE_RETRIES
    assert mock_sleep.call_count == notifications.LOCK_ACQUIRE_RETRIES


def test_acquire_lock_retries_then_succeeds():
    with (
        patch(
            "envergo.tchap.notifications.cache.add", side_effect=[False, True]
        ) as mock_add,
        patch("envergo.tchap.notifications.time.sleep") as mock_sleep,
    ):
        assert notifications._acquire_lock("token-a") is True
    assert mock_add.call_count == 2
    mock_sleep.assert_called_once()


def test_release_lock_ignores_a_lock_it_does_not_own():
    cache.set(notifications.LOCK_KEY, "someone-else", timeout=30)
    notifications._release_lock("token-a")
    assert cache.get(notifications.LOCK_KEY) == "someone-else"


def test_release_lock_deletes_its_own_lock():
    cache.set(notifications.LOCK_KEY, "token-a", timeout=30)
    notifications._release_lock("token-a")
    assert cache.get(notifications.LOCK_KEY) is None


def test_release_lock_deletes_when_the_holder_reads_back_as_none():
    """A None read must still delete: production runs the cache with
    IGNORE_EXCEPTIONS, so a Redis blip reads as None rather than raising, and
    skipping the delete would wedge every sender until LOCK_TIMEOUT.
    """
    with (
        patch("envergo.tchap.notifications.cache.get", return_value=None),
        patch("envergo.tchap.notifications.cache.delete") as mock_delete,
    ):
        notifications._release_lock("token-a")

    mock_delete.assert_called_once_with(notifications.LOCK_KEY)


def test_notify_with_lock_calls_store_and_releases():
    row = _make_credentials()
    with patch("envergo.tchap.notifications._notify_with_store") as mock_store:
        notifications._notify_with_lock("hello", "!room:example.org")

    args, _ = mock_store.call_args
    assert args[:2] == ("hello", "!room:example.org")
    assert args[2].pk == row.pk
    assert cache.get(notifications.LOCK_KEY) is None


def test_notify_with_lock_reads_the_credentials_under_the_lock():
    """The row is fetched inside the critical section, never before it.

    The crypto store travels on that row, so a read taken before the lock
    could already be a generation behind by the time the store is saved back.
    """
    _make_credentials()
    seen = {}
    real_get_credentials = notifications.get_credentials

    def spy():
        seen["lock_held_at_read"] = cache.get(notifications.LOCK_KEY)
        return real_get_credentials()

    with (
        patch("envergo.tchap.notifications.get_credentials", side_effect=spy),
        patch("envergo.tchap.notifications._notify_with_store"),
    ):
        notifications._notify_with_lock("hello", "!room:example.org")

    assert seen["lock_held_at_read"] is not None


def test_notify_with_lock_skips_store_when_not_bootstrapped():
    """No credentials row: nothing to send, and the lock is handed back."""
    with patch("envergo.tchap.notifications._notify_with_store") as mock_store:
        notifications._notify_with_lock("hello", "!room:example.org")

    mock_store.assert_not_called()
    assert cache.get(notifications.LOCK_KEY) is None


def test_notify_with_lock_releases_even_on_failure():
    _make_credentials()
    with patch(
        "envergo.tchap.notifications._notify_with_store", side_effect=Exception("boom")
    ):
        with pytest.raises(Exception):
            notifications._notify_with_lock("hello", "!room:example.org")
    assert cache.get(notifications.LOCK_KEY) is None


def test_notify_with_lock_skips_store_when_lock_unavailable(caplog):
    """The drop is accepted, but it must be loud enough to reach Sentry."""
    _make_credentials()
    with (
        patch("envergo.tchap.notifications._acquire_lock", return_value=False),
        patch("envergo.tchap.notifications._notify_with_store") as mock_store,
    ):
        notifications._notify_with_lock("hello", "!room:example.org")
    mock_store.assert_not_called()

    record = next(r for r in caplog.records if "crypto store lock" in r.message)
    assert record.levelname == "ERROR"
    assert record.room_id == "!room:example.org"


# ---- _notify_with_store (checkpoint, DB-backed) --------------------------

db_name = f"{CREDS.user_id}_{CREDS.device_id}.db"


def _stored_blob():
    row = TchapCredential.objects.get()
    return bytes(row.crypto_store) if row.crypto_store else None


def test_consecutive_sends_each_start_from_the_latest_store():
    """Every send picks up the store the previous one checkpointed.

    This is what the lock exists for: reading the row before taking it would
    let a second sender start from a generation that is already superseded and
    write it back, dropping the Olm/Megolm sessions the first one established.
    """
    _make_credentials(crypto_store=b"gen-1")
    loaded = []

    async def fake_send(msg, room_id, store_path, creds):
        db_file = Path(store_path) / db_name
        loaded.append(db_file.read_bytes())
        db_file.write_bytes(f"gen-{len(loaded) + 1}".encode())
        return True

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_lock("hello", "!room:example.org")
        notifications._notify_with_lock("hello", "!room:example.org")

    assert loaded == [b"gen-1", b"gen-2"]
    assert _stored_blob() == b"gen-3"


def test_notify_with_store_loads_existing_blob_before_send():
    row = _make_credentials(crypto_store=b"previous-state")
    seen = {}

    async def fake_send(msg, room_id, store_path, creds):
        seen["content"] = (Path(store_path) / db_name).read_bytes()

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_store("hello", "!room:example.org", row)

    assert seen["content"] == b"previous-state"


def test_notify_with_store_skips_load_when_no_existing_blob():
    row = _make_credentials(crypto_store=None)
    seen = {}

    async def fake_send(msg, room_id, store_path, creds):
        seen["exists"] = (Path(store_path) / db_name).exists()

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_store("hello", "!room:example.org", row)

    assert seen["exists"] is False


def test_notify_with_store_saves_state_after_successful_send():
    row = _make_credentials(crypto_store=None)

    async def fake_send(msg, room_id, store_path, creds):
        (Path(store_path) / db_name).write_bytes(b"new-state")
        return True

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_store("hello", "!room:example.org", row)

    assert _stored_blob() == b"new-state"


def test_notify_with_store_saves_state_even_if_bootstrap_send_fails():
    """A failed first send still persists the freshly created olm account.

    Otherwise nio would mint a new device identity on the next attempt.
    """
    row = _make_credentials(crypto_store=None)

    async def fake_send(msg, room_id, store_path, creds):
        (Path(store_path) / db_name).write_bytes(b"fresh-account")
        raise Exception("boom")

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_store(
            "hello", "!room:example.org", row
        )  # must not raise

    assert _stored_blob() == b"fresh-account"


def test_notify_with_store_keeps_good_store_when_send_fails():
    """A failed send against an existing (good) store must NOT overwrite it.

    Persisting post-failure state is how the device gets wedged and starts
    emitting messages recipients can no longer decrypt.
    """
    row = _make_credentials(crypto_store=b"good-state")

    async def fake_send(msg, room_id, store_path, creds):
        (Path(store_path) / db_name).write_bytes(b"partial-state")
        raise Exception("boom")

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_store(
            "hello", "!room:example.org", row
        )  # must not raise

    assert _stored_blob() == b"good-state"


def test_notify_with_store_saves_state_on_success_with_existing_store():
    """A clean send against an existing store does checkpoint its progress."""
    row = _make_credentials(crypto_store=b"good-state")

    async def fake_send(msg, room_id, store_path, creds):
        (Path(store_path) / db_name).write_bytes(b"advanced-state")
        return True

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_store("hello", "!room:example.org", row)

    assert _stored_blob() == b"advanced-state"


def test_notify_with_store_warns_when_a_good_send_persists_nothing(caplog):
    """A send that works but leaves no store file means nothing is checkpointed.

    Silently doing nothing here would hide a device minted afresh on every
    single notification.
    """
    row = _make_credentials(crypto_store=None)

    async def fake_send(msg, room_id, store_path, creds):
        return True

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_store("hello", "!room:example.org", row)

    assert _stored_blob() is None
    assert "no crypto store was written" in caplog.text


def test_notify_with_store_skips_save_if_nio_never_wrote_anything():
    row = _make_credentials(crypto_store=None)

    async def fake_send(msg, room_id, store_path, creds):
        raise Exception("boom before nio touched the store")

    with patch("envergo.tchap.notifications._send", side_effect=fake_send):
        notifications._notify_with_store("hello", "!room:example.org", row)

    assert _stored_blob() is None


# ---- _send() (nio mocked, no network) -------------------------------------


def test_send_happy_path(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(rooms={room_id: MagicMock()})

    with patch(
        "envergo.tchap.notifications.AsyncClient", return_value=client
    ) as mock_cls:
        asyncio.run(notifications._send("**hello**", room_id, str(tmp_path), CREDS))

    mock_cls.assert_called_once_with(
        homeserver=settings.TCHAP_HOMESERVER_URL,
        user=CREDS.user_id,
        device_id=CREDS.device_id,
        store_path=str(tmp_path),
        config=ANY,
    )
    client.restore_login.assert_called_once_with(
        user_id=CREDS.user_id,
        device_id=CREDS.device_id,
        access_token=CREDS.access_token,
    )
    # No sync_filter: an earlier attempt at scoping the sync to just the
    # target room made Tchap stop returning it as joined at all.
    _, sync_kwargs = client.sync.call_args
    assert "sync_filter" not in sync_kwargs
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


def test_send_converts_mattermost_style_emoji_shortcodes(settings, tmp_path):
    """Convert Mattermost-style shortcodes to real Unicode emoji for Tchap.

    Mattermost renders :x:/:warning: itself; unknown/custom shortcodes are
    left untouched.
    """
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(rooms={room_id: MagicMock()})

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        asyncio.run(
            notifications._send(":x: erreur :icon-info:", room_id, str(tmp_path), CREDS)
        )

    _, kwargs = client.room_send.call_args
    assert kwargs["content"]["body"] == "❌ erreur :icon-info:"
    assert "❌ erreur :icon-info:" in kwargs["content"]["formatted_body"]


def test_send_renders_the_mattermost_style_templates(settings, tmp_path):
    """Single newlines are line breaks and ``` fences are code blocks.

    The notification templates are written for Mattermost's renderer; plain
    python-markdown would run each of them into one paragraph and print the
    fences literally.
    """
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(rooms={room_id: MagicMock()})
    msg = "N° de dossier : 42\nDate : hier\n\n```\ndump\n```"

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        asyncio.run(notifications._send(msg, room_id, str(tmp_path), CREDS))

    _, kwargs = client.room_send.call_args
    formatted = kwargs["content"]["formatted_body"]
    assert "N° de dossier : 42<br />" in formatted
    assert "<code>" in formatted and "```" not in formatted
    # The plain-text fallback keeps the message exactly as the template wrote it.
    assert kwargs["content"]["body"] == msg


def test_send_pins_the_crypto_store_filename(settings, tmp_path):
    """nio is told which store file to use instead of defaulting to its own.

    `_notify_with_store` restores and re-reads the blob under that same name,
    so a nio default rename would otherwise silently mint a new device on
    every send.
    """
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(rooms={room_id: MagicMock()})

    with patch(
        "envergo.tchap.notifications.AsyncClient", return_value=client
    ) as mock_cls:
        asyncio.run(notifications._send("hello", room_id, str(tmp_path), CREDS))

    _, kwargs = mock_cls.call_args
    assert kwargs["config"].store_name == notifications.store_name(
        CREDS.user_id, CREDS.device_id
    )


def test_send_uploads_keys_when_needed(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(should_upload_keys=True, rooms={room_id: MagicMock()})

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        asyncio.run(notifications._send("hello", room_id, str(tmp_path), CREDS))

    client.keys_upload.assert_called_once()


def test_send_returns_early_on_sync_error(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(sync_return=SyncError("boom"))

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        asyncio.run(notifications._send("hello", room_id, str(tmp_path), CREDS))

    client.room_send.assert_not_called()
    client.close.assert_called_once()


def test_send_returns_early_when_room_not_joined(settings, tmp_path):
    """Neither joined nor invited: unchanged behavior, no join attempted."""
    client = _mock_nio_client(rooms={}, invited_rooms={})

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        asyncio.run(
            notifications._send(
                "hello", settings.TCHAP_ROOM_ID_AMENAGEMENT, str(tmp_path), CREDS
            )
        )

    client.join.assert_not_called()
    client.room_send.assert_not_called()
    client.close.assert_called_once()


def test_send_accepts_pending_invite_and_resyncs(settings, tmp_path):
    """A room the bot was invited to (but never accepted) gets joined.

    A follow-up sync then picks up its state, and the send goes through.
    """
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(rooms={}, invited_rooms={room_id: MagicMock()})

    async def fake_sync(*args, **kwargs):
        # The 2nd sync (post-join) is what makes nio learn the room is now
        # joined, mirroring real nio behavior: join() alone doesn't.
        if client.sync.await_count == 2:
            client.rooms[room_id] = MagicMock()
        return MagicMock()

    client.sync = AsyncMock(side_effect=fake_sync)

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        asyncio.run(notifications._send("hello", room_id, str(tmp_path), CREDS))

    client.join.assert_called_once_with(room_id)
    assert client.sync.await_count == 2
    _, second_sync_kwargs = client.sync.call_args
    assert second_sync_kwargs["full_state"] is False
    client.room_send.assert_called_once()
    client.close.assert_called_once()


def test_send_returns_early_when_join_fails(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(
        rooms={}, invited_rooms={room_id: MagicMock()}, join_return=JoinError("boom")
    )

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        asyncio.run(notifications._send("hello", room_id, str(tmp_path), CREDS))

    client.join.assert_called_once_with(room_id)
    assert client.sync.await_count == 1  # no follow-up sync attempted
    client.room_send.assert_not_called()
    client.close.assert_called_once()


def test_send_logs_room_send_error_without_raising(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(
        rooms={room_id: MagicMock()}, room_send_return=RoomSendError("boom")
    )

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        asyncio.run(
            notifications._send("hello", room_id, str(tmp_path), CREDS)
        )  # must not raise

    client.close.assert_called_once()


def test_send_closes_client_even_if_sync_raises(settings, tmp_path):
    client = _mock_nio_client()
    client.sync = AsyncMock(side_effect=RuntimeError("network exploded"))

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        with pytest.raises(RuntimeError):
            asyncio.run(
                notifications._send(
                    "hello", settings.TCHAP_ROOM_ID_AMENAGEMENT, str(tmp_path), CREDS
                )
            )

    client.close.assert_called_once()


# ---- _send() success signalling (drives the checkpoint) -------------------


def test_send_returns_true_on_success(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(rooms={room_id: MagicMock()})

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        assert (
            asyncio.run(notifications._send("hello", room_id, str(tmp_path), CREDS))
            is True
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"sync_return": SyncError("boom")},
        {"rooms": {}, "invited_rooms": {}},
        {
            "rooms": {},
            "invited_rooms": {"!x": MagicMock()},
            "join_return": JoinError("boom"),
        },
    ],
)
def test_send_returns_false_when_it_bails_out(settings, tmp_path, overrides):
    room_id = "!x"
    client = _mock_nio_client(**overrides)

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        assert (
            asyncio.run(notifications._send("hello", room_id, str(tmp_path), CREDS))
            is False
        )


def test_send_returns_false_on_room_send_error(settings, tmp_path):
    room_id = settings.TCHAP_ROOM_ID_AMENAGEMENT
    client = _mock_nio_client(
        rooms={room_id: MagicMock()}, room_send_return=RoomSendError("boom")
    )

    with patch("envergo.tchap.notifications.AsyncClient", return_value=client):
        assert (
            asyncio.run(notifications._send("hello", room_id, str(tmp_path), CREDS))
            is False
        )


# ---- primary/backup contract --------------------------------------------


def test_mattermost_notify_does_not_call_tchap():
    """Tchap is the primary channel and calls Mattermost, not the other way
    around: mattermost.notify() must only ever talk to Mattermost.
    """
    with patch("envergo.tchap.notifications.deliver") as mock_tchap_notify:
        mattermost.notify("hello", "amenagement")

    mock_tchap_notify.assert_not_called()
