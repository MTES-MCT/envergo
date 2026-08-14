import asyncio
import logging
import secrets
import tempfile
import time
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from nio import AsyncClient, AsyncClientConfig, RoomSendError, SyncError

from envergo.utils import mattermost
from envergo.utils.markdown import markdown_to_html

logger = logging.getLogger(__name__)

# Long-poll budget for sync(), in ms. Kept short: we're not a persistent bot
# loop, we just need current room/key state, not to wait for new messages.
SYNC_TIMEOUT = 3000

# Hard wall-clock budget, in seconds, for the whole Tchap exchange. nio
# retries connection timeouts with an unbounded backoff by default; without
# this, a Tchap outage would hang the calling request or Celery task forever.
NOTIFY_TIMEOUT = 20

# Mutual-exclusion lock around the crypto store checkpoint: two workers must
# never read-modify-write the same device's E2EE state concurrently, or its
# sessions get corrupted. cache.add()/cache.delete() (not django-redis's
# cache.lock(), unavailable on the LocMemCache backend used in dev/test)
# works identically against Redis in production and in-memory locally.
LOCK_KEY = "tchap:crypto-store-lock"
LOCK_TIMEOUT = NOTIFY_TIMEOUT + 10  # self-heals if a holder dies without releasing
LOCK_ACQUIRE_RETRIES = 5
LOCK_ACQUIRE_DELAY = 1  # seconds


def notify(msg, site):
    """Send a message to a Tchap room, E2E encrypted, then relay it to Mattermost.

    Fire-and-forget: a failure is logged but never raised
    Mattermost is always attempted regardless of how the
    Tchap send went.

    `msg` is markdown text, converted to HTML for the Tchap formatted body.
    """
    room_id = (
        settings.TCHAP_ROOM_ID_HAIE
        if site == "haie"
        else settings.TCHAP_ROOM_ID_AMENAGEMENT
    )
    if not settings.TCHAP_ACCESS_TOKEN or not room_id:
        logger.warning(
            f"No tchap configuration for site {site}. Doing nothing. Message: {msg}"
        )
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
        _notify_with_store(msg, room_id)
    finally:
        _release_lock(token)


def _acquire_lock(token):
    for _ in range(LOCK_ACQUIRE_RETRIES):
        if cache.add(LOCK_KEY, token, timeout=LOCK_TIMEOUT):
            return True
        time.sleep(LOCK_ACQUIRE_DELAY)
    return False


def _release_lock(token):
    # Only release if we still hold it: avoids deleting a lock some other
    # process has since acquired after ours expired. Not perfectly atomic,
    # but a real improvement over a bare cache.delete(), and this lock is
    # rarely contended.
    if cache.get(LOCK_KEY) == token:
        cache.delete(LOCK_KEY)


def _notify_with_store(msg, room_id):
    """Run the Tchap exchange with nio's crypto store checked out from storage."""
    storage = storages["tchap"]
    device_id = settings.TCHAP_DEVICE_ID
    db_name = f"{settings.TCHAP_USER_ID}_{device_id}.db"

    with tempfile.TemporaryDirectory() as store_path:
        db_file = Path(store_path) / db_name
        if storage.exists(db_name):
            with storage.open(db_name, "rb") as f:
                db_file.write_bytes(f.read())
        try:
            asyncio.run(
                asyncio.wait_for(
                    _send(msg, room_id, store_path), timeout=NOTIFY_TIMEOUT
                )
            )
        except Exception as e:
            logger.warning(
                "Could not send the tchap notification", extra={"exception": e}
            )
        finally:
            # Checkpoint whatever local state exists, even on failure: a
            # freshly created olm account is written to disk as soon as nio
            # logs in, well before any network call. Losing it would make
            # nio recreate a brand new device identity next time, which
            # Tchap would treat as a suspicious device change.
            if db_file.exists():
                storage.save(db_name, ContentFile(db_file.read_bytes()))


async def _send(msg, room_id, store_path):
    client = AsyncClient(
        homeserver=settings.TCHAP_HOMESERVER_URL,
        user=settings.TCHAP_USER_ID,
        device_id=settings.TCHAP_DEVICE_ID,
        store_path=store_path,
        config=AsyncClientConfig(encryption_enabled=True, store_sync_tokens=True),
    )
    try:
        client.restore_login(
            user_id=settings.TCHAP_USER_ID,
            device_id=settings.TCHAP_DEVICE_ID,
            access_token=settings.TCHAP_ACCESS_TOKEN,
        )

        # Sync to learn joined rooms/encryption state and process pending
        # key shares. Full state only on the very first sync ever; after
        # that the persisted sync token resumes incrementally.
        sync_resp = await client.sync(
            timeout=SYNC_TIMEOUT, full_state=not client.loaded_sync_token
        )
        if isinstance(sync_resp, SyncError):
            logger.warning(f"Could not sync with tchap: {sync_resp}")
            return

        if client.should_upload_keys:
            await client.keys_upload()

        if room_id not in client.rooms:
            logger.warning(
                f"Tchap room {room_id} is not joined by the bot account, "
                "cannot send notification"
            )
            return

        content = {
            "msgtype": "m.text",
            "body": msg,
            "format": "org.matrix.custom.html",
            "formatted_body": markdown_to_html(msg),
        }
        # room_send encrypts automatically for encrypted rooms. The bot never
        # runs a device verification flow, so devices are always "unverified";
        # ignore that or messages would stop going out as people add devices.
        resp = await client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=content,
            ignore_unverified_devices=True,
        )
        if isinstance(resp, RoomSendError):
            logger.warning(f"Could not send the tchap notification: {resp}")
    finally:
        await client.close()
