"""Shared safety helpers for the geodata management commands.

Lives outside the `commands/` directory so Django's command auto-discovery
doesn't try to load it as a manage.py subcommand.

Centralises three things every command that touches a database the operator
might mistake for production needs:

- a destination-DB identifier so the operator can verify the target before
  confirming a destructive action;
- a refusal-to-run guard for production-flavoured settings modules;
- the set of valid map_type / data_type keys, used both for argparse choices
  and CSV validation.
"""

import os

from django.conf import settings
from django.core.management.base import CommandError

from envergo.geodata.models import DATA_TYPES, MAP_TYPES


VALID_MAP_TYPES = {t[0] for t in MAP_TYPES}
VALID_DATA_TYPES = {t[0] for t in DATA_TYPES}


def get_default_db_identity():
    """Return a 'dbname @ host:port' string for Django's default database."""
    db = settings.DATABASES["default"]
    name = db.get("NAME") or "?"
    host = db.get("HOST") or "localhost"
    port = db.get("PORT") or "5432"
    return f"{name} @ {host}:{port}"


def refuse_production_settings():
    """Abort if DJANGO_SETTINGS_MODULE looks like a production module.

    Cheap early guard against the wrong-terminal mistake. Commands that
    open a separate prod connection (copy_geometries_to_prod) also do a
    server-side identity comparison once both connections are open; this
    helper just catches the obvious case before any work happens.
    """
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if "production" in settings_module:
        raise CommandError(
            f"Refusing to run with DJANGO_SETTINGS_MODULE="
            f"{settings_module!r}. This command is meant to be run from "
            f"a developer machine pointing at a local database."
        )
