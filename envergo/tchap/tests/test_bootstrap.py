from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from envergo.tchap.models import TchapCredential

pytestmark = pytest.mark.django_db

CMD = "envergo.tchap.management.commands.tchap_bootstrap"


@pytest.fixture(autouse=True)
def bootstrap_settings(settings):
    settings.TCHAP_HOMESERVER_URL = "https://tchap.example.org"
    settings.TCHAP_USER_ID = "@bot:example.org"
    settings.TCHAP_BOT_PASSWORD = "s3cret"  # pragma: allowlist secret
    settings.TCHAP_ROOM_ID_HAIE = "!haie:example.org"
    settings.TCHAP_ROOM_ID_AMENAGEMENT = "!am:example.org"
    return settings


def _fake_client_factory(
    device_id="NEWDEV",
    access_token="new-token",
    rooms=("!haie:example.org", "!am:example.org"),
):
    """Return (factory, client) for patching AsyncClient.

    The factory writes a fake nio store file into whatever store_path it is
    constructed with, so the command's on-disk check passes.
    """
    client = MagicMock()
    client.device_id = device_id
    client.access_token = access_token
    client.should_upload_keys = True
    client.rooms = {r: MagicMock() for r in rooms}
    client.invited_rooms = {}
    client.login = AsyncMock(return_value=MagicMock())
    client.sync = AsyncMock(return_value=MagicMock())
    client.keys_upload = AsyncMock()
    client.join = AsyncMock(return_value=MagicMock())
    client.room_send = AsyncMock(return_value=MagicMock())
    client.close = AsyncMock()

    def factory(**kwargs):
        store_path = kwargs["store_path"]
        (Path(store_path) / f"@bot:example.org_{device_id}.db").write_bytes(b"store")
        return client

    return factory, client


def _run(**options):
    out, err = StringIO(), StringIO()
    call_command("tchap_bootstrap", stdout=out, stderr=err, **options)
    return out.getvalue()


def test_bootstrap_missing_password_errors(settings):
    settings.TCHAP_BOT_PASSWORD = None
    with pytest.raises(CommandError, match="TCHAP_BOT_PASSWORD"):
        _run()


def test_bootstrap_refuses_when_credentials_exist_without_force():
    TchapCredential.objects.create(
        user_id="@bot:example.org", device_id="OLD", access_token="old"
    )
    with patch(f"{CMD}.AsyncClient") as mock_cls:
        with pytest.raises(CommandError, match="already exist"):
            _run()
    mock_cls.assert_not_called()  # never even attempts a login


def test_bootstrap_persists_credentials_and_store_blob():
    factory, client = _fake_client_factory()
    with patch(f"{CMD}.AsyncClient", side_effect=factory):
        _run()

    row = TchapCredential.objects.get()
    assert row.device_id == "NEWDEV"
    assert row.access_token == "new-token"
    assert row.user_id == "@bot:example.org"
    assert bytes(row.crypto_store) == b"store"

    client.keys_upload.assert_awaited_once()
    assert client.room_send.await_count == 2  # warms both configured rooms


def test_bootstrap_warms_only_joined_rooms():
    factory, client = _fake_client_factory(rooms=("!haie:example.org",))
    with patch(f"{CMD}.AsyncClient", side_effect=factory):
        _run()

    client.room_send.assert_awaited_once()  # the unjoined room is skipped


def test_bootstrap_force_replaces_existing_single_row():
    TchapCredential.objects.create(
        user_id="@bot:example.org", device_id="OLD", access_token="old"
    )
    factory, _ = _fake_client_factory(device_id="FRESH", access_token="fresh-token")
    with patch(f"{CMD}.AsyncClient", side_effect=factory):
        _run(force=True)

    row = TchapCredential.objects.get()  # exactly one row remains
    assert row.device_id == "FRESH"
    assert row.access_token == "fresh-token"
    assert bytes(row.crypto_store) == b"store"


def test_bootstrap_skips_test_message_when_requested():
    factory, client = _fake_client_factory()
    with patch(f"{CMD}.AsyncClient", side_effect=factory):
        _run(no_test_message=True)

    client.room_send.assert_not_awaited()
    assert TchapCredential.objects.count() == 1
