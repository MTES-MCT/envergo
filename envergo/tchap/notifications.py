import asyncio
import logging
import secrets
import tempfile
import time
from pathlib import Path

import emoji
from django.conf import settings
from django.core.cache import cache
from nio import AsyncClient, AsyncClientConfig, JoinError, RoomSendError, SyncError

from envergo.tchap.models import TchapCredential
from envergo.utils import mattermost
from envergo.utils.markdown import markdown_to_html

logger = logging.getLogger(__name__)

# sync() long-poll budget (ms); short, we only need current state.
SYNC_TIMEOUT = 3000

NOTIFY_TIMEOUT = 20

LOCK_KEY = "tchap:crypto-store-lock"
LOCK_TIMEOUT = NOTIFY_TIMEOUT + 30
LOCK_ACQUIRE_RETRIES = 5
LOCK_ACQUIRE_DELAY = 1


def get_credentials():
    """The bot's `TchapCredential` row, or None if never bootstrapped."""
    return TchapCredential.objects.order_by("-pk").first()


def store_name(user_id, device_id):
    """Name of the SQLite file nio keeps its crypto store in."""
    return f"{user_id}_{device_id}.db"


def deliver(msg, site):
    """Send `msg` to a Tchap room, E2E-encrypted, then relay to Mattermost.

    `msg` is markdown. Fire-and-forget: failures are logged, never raised.

    This blocks for as long as the crypto store lock and the Tchap exchange
    take, so it runs in a Celery worker: see `envergo.tchap.tasks.notify` for
    the entry point every caller should use.
    """
    room_id = (
        settings.TCHAP_ROOM_ID_HAIE
        if site == "haie"
        else settings.TCHAP_ROOM_ID_AMENAGEMENT
    )
    if not room_id:
        logger.warning(f"No tchap room for site {site}. Doing nothing. Message: {msg}")
    else:
        try:
            _notify_with_lock(msg, room_id)
        except Exception as e:
            logger.warning(
                "Could not send the tchap notification", extra={"exception": e}
            )

    mattermost.notify(msg, site)


def _notify_with_lock(msg, room_id):
    token = secrets.token_hex(8)
    if not _acquire_lock(token):
        logger.warning("Could not acquire the tchap crypto store lock, skipping")
        return
    try:
        # Read the credentials under the lock: the row carries the crypto store
        # that _notify_with_store writes back, so a read taken before the lock
        # could already be a generation behind by the time we save it.
        creds = get_credentials()
        if not creds or not creds.access_token:
            logger.warning(f"Tchap is not bootstrapped. Message: {msg}")
            return
        _notify_with_store(msg, room_id, creds)
    finally:
        _release_lock(token)


def _acquire_lock(token):
    for _ in range(LOCK_ACQUIRE_RETRIES):
        if cache.add(LOCK_KEY, token, timeout=LOCK_TIMEOUT):
            return True
        time.sleep(LOCK_ACQUIRE_DELAY)
    return False


def _release_lock(token):
    """Release the lock unless it demonstrably belongs to someone else."""
    holder = cache.get(LOCK_KEY)
    if holder is None or holder == token:
        cache.delete(LOCK_KEY)


def _notify_with_store(msg, room_id, creds):
    """Run the Tchap exchange with nio's crypto store checked out from the DB."""
    db_name = store_name(creds.user_id, creds.device_id)

    existing_store = bytes(creds.crypto_store) if creds.crypto_store else None
    had_existing_store = existing_store is not None

    with tempfile.TemporaryDirectory() as store_path:
        db_file = Path(store_path) / db_name
        if had_existing_store:
            db_file.write_bytes(existing_store)
        send_ok = False
        try:
            send_ok = asyncio.run(
                asyncio.wait_for(
                    _send(msg, room_id, store_path, creds), timeout=NOTIFY_TIMEOUT
                )
            )
        except Exception as e:
            logger.warning(
                "Could not send the tchap notification", extra={"exception": e}
            )
        finally:
            # Checkpoint only on a clean send, or on first bootstrap (must keep
            # the freshly minted olm account or nio changes device identity).
            # Never overwrite a good store with partial/failed state: nio does
            # not persist outbound Megolm sessions, so a partial run can only
            # wedge it, leaving recipients unable to decrypt.
            if db_file.exists() and (send_ok or not had_existing_store):
                creds.crypto_store = db_file.read_bytes()
                creds.save(update_fields=["crypto_store", "updated_at"])
            elif send_ok:
                logger.warning(
                    f"Tchap send succeeded but no crypto store was written at "
                    f"{db_name}; the session is not being persisted."
                )


async def _send(msg, room_id, store_path, creds):
    """Return True only if the message was actually accepted by the server."""
    client = AsyncClient(
        homeserver=settings.TCHAP_HOMESERVER_URL,
        user=creds.user_id,
        device_id=creds.device_id,
        store_path=store_path,
        config=AsyncClientConfig(
            encryption_enabled=True,
            store_sync_tokens=True,
            store_name=store_name(creds.user_id, creds.device_id),
        ),
    )
    try:
        client.restore_login(
            user_id=creds.user_id,
            device_id=creds.device_id,
            access_token=creds.access_token,
        )

        # Learn joined rooms/encryption state; full state only on the first sync.
        sync_resp = await client.sync(
            timeout=SYNC_TIMEOUT, full_state=not client.loaded_sync_token
        )
        if isinstance(sync_resp, SyncError):
            logger.warning(f"Could not sync with tchap: {sync_resp}")
            return False

        if client.should_upload_keys:
            await client.keys_upload()

        if room_id not in client.rooms and room_id in client.invited_rooms:
            # Invited but not joined yet: accept, then re-sync to pick up the
            # room (join() alone doesn't populate client.rooms).
            join_resp = await client.join(room_id)
            if isinstance(join_resp, JoinError):
                logger.warning(f"Could not join tchap room {room_id}: {join_resp}")
                return False
            sync_resp = await client.sync(timeout=SYNC_TIMEOUT, full_state=False)
            if isinstance(sync_resp, SyncError):
                logger.warning(f"Could not sync with tchap after joining: {sync_resp}")
                return False

        if room_id not in client.rooms:
            logger.warning(
                f"Tchap room {room_id} is not joined by the bot account, cannot "
                f"send notification. Joined rooms: {list(client.rooms)}. "
                f"Invited rooms: {list(client.invited_rooms)}."
            )
            return False

        # Tchap doesn't render :x:-style shortcodes like Mattermost does.
        msg_with_emoji = emoji.emojize(msg, language="alias")
        content = {
            "msgtype": "m.text",
            "body": msg_with_emoji,
            "format": "org.matrix.custom.html",
            "formatted_body": markdown_to_html(msg_with_emoji, "nl2br", "fenced_code"),
        }
        # Encrypts automatically. The bot never verifies devices, so ignore
        # unverified ones or sends would stop as members add devices.
        resp = await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content,
            ignore_unverified_devices=True,
        )
        if isinstance(resp, RoomSendError):
            logger.warning(f"Could not send the tchap notification: {resp}")
            return False

        return True
    finally:
        await client.close()
