import asyncio
import logging
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from nio import (
    AsyncClient,
    AsyncClientConfig,
    JoinError,
    LoginError,
    RoomSendError,
    SyncError,
)

from envergo.tchap.models import TchapCredential
from envergo.tchap.notifications import SYNC_TIMEOUT

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Provision a fresh Tchap bot session: single-process password login "
        "(mints a new device the bot owns), key upload, join and warm every "
        "configured room with a test message, then persist the device_id, "
        "access_token and nio crypto store to the database. Run once by an "
        "operator; the notification path reads the DB row. Refuses to run if a "
        "session exists unless --force (each run mints a new device)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-provision even if credentials already exist in the DB.",
        )
        parser.add_argument(
            "--no-test-message",
            action="store_true",
            help="Only join the rooms; skip the warming test message.",
        )

    def handle(self, *args, **options):
        if not settings.TCHAP_BOT_PASSWORD:
            raise CommandError("DJANGO_TCHAP_BOT_PASSWORD is not configured.")
        if not settings.TCHAP_USER_ID or not settings.TCHAP_HOMESERVER_URL:
            raise CommandError(
                "TCHAP_USER_ID / TCHAP_HOMESERVER_URL are not configured."
            )

        if TchapCredential.objects.exists() and not options["force"]:
            raise CommandError(
                "Tchap credentials already exist. Re-running mints a NEW device; "
                "pass --force if that is really what you want."
            )

        rooms = [
            r
            for r in (settings.TCHAP_ROOM_ID_HAIE, settings.TCHAP_ROOM_ID_AMENAGEMENT)
            if r
        ]

        device_id, access_token, crypto_store = asyncio.run(
            self._bootstrap(rooms, send_test=not options["no_test_message"])
        )

        TchapCredential.objects.all().delete()
        TchapCredential.objects.create(
            user_id=settings.TCHAP_USER_ID,
            device_id=device_id,
            access_token=access_token,
            crypto_store=crypto_store,
        )

        self.stdout.write(self.style.SUCCESS("Tchap bot bootstrapped."))
        self.stdout.write(f"user_id  : {settings.TCHAP_USER_ID}")
        self.stdout.write(f"device_id: {device_id}")
        self.stdout.write(
            "Credentials and crypto store saved to the database; the "
            "notification path will use them on the next send. No env change or "
            "redeploy is required."
        )

    async def _bootstrap(self, rooms, send_test):
        with tempfile.TemporaryDirectory() as store_path:
            client = AsyncClient(
                homeserver=settings.TCHAP_HOMESERVER_URL,
                user=settings.TCHAP_USER_ID,
                store_path=store_path,
                config=AsyncClientConfig(
                    encryption_enabled=True, store_sync_tokens=True
                ),
            )
            try:
                login_resp = await client.login(
                    settings.TCHAP_BOT_PASSWORD, device_name="envergo-bot"
                )
                if isinstance(login_resp, LoginError):
                    raise CommandError(f"Login failed: {login_resp}")

                device_id = client.device_id
                access_token = client.access_token

                sync_resp = await client.sync(timeout=SYNC_TIMEOUT, full_state=True)
                if isinstance(sync_resp, SyncError):
                    raise CommandError(f"Sync failed: {sync_resp}")

                if client.should_upload_keys:
                    await client.keys_upload()

                for room_id in rooms:
                    if room_id not in client.rooms and room_id in client.invited_rooms:
                        join_resp = await client.join(room_id)
                        if isinstance(join_resp, JoinError):
                            self.stderr.write(f"Could not join {room_id}: {join_resp}")
                            continue
                        await client.sync(timeout=SYNC_TIMEOUT, full_state=False)

                if send_test:
                    # A real send establishes Olm sessions and shares the Megolm
                    # key, warming the room so the notify path stays incremental.
                    for room_id in rooms:
                        if room_id not in client.rooms:
                            self.stderr.write(f"Room {room_id} not joined; skipping.")
                            continue
                        resp = await client.room_send(
                            room_id=room_id,
                            message_type="m.room.message",
                            content={
                                "msgtype": "m.text",
                                "body": ":white_check_mark: Bot Tchap réinitialisé "
                                "(message de test).",
                            },
                            ignore_unverified_devices=True,
                        )
                        if isinstance(resp, RoomSendError):
                            self.stderr.write(
                                f"Test message to {room_id} failed: {resp}"
                            )

                db_name = f"{settings.TCHAP_USER_ID}_{device_id}.db"
                db_file = Path(store_path) / db_name
                if not db_file.exists():
                    raise CommandError(
                        f"nio did not write a store file at {db_file}; aborting."
                    )

                return device_id, access_token, db_file.read_bytes()
            finally:
                await client.close()
