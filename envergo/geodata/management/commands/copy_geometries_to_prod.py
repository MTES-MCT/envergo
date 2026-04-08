"""Copy Maps and their Zones/Lines from a local database to production.

Designed for one-shot bulk imports of large datasets that can't be processed
inside a Scalingo one-off container session (e.g. the BD Haie ~20M lines or
the 1500+ "terres émergées" polygon files).

═══════════════════════════════════════════════════════════════════════
DESTRUCTIVE — READ THIS BEFORE RUNNING
═══════════════════════════════════════════════════════════════════════

This command DELETES rows from the production database and replaces them
with rows from a local database. It is ONLY safe to run if BOTH of the
following hold for the entire duration of the operation:

  1. The local DB was JUST imported against a FRESH dump of production.
     Any rows that production created after the dump was taken will be
     silently destroyed by the DELETE phase.

  2. Map creation has been BLOCKED on production for the entire duration
     of the run (no admin uploads, no API ingest, no Celery jobs creating
     Maps). New rows would either be deleted or cause id collisions.

Cascading deletes: removing a Map row also removes every row in
geodata_zone, geodata_line, hedges_speciesmap, and any other table whose
foreign key to geodata_map declares ON DELETE CASCADE. Verify that no
production data outside the targeted map_type depends on the maps you are
about to replace.

Only Maps with import_status='success' on local are eligible. Failed,
partial, or never-processed local maps are silently excluded — pushing
them would propagate broken data to production. The skipped count is
surfaced in the warning banner.

The command runs in three phases:

1. Phase 1 (atomic): DELETE the previous import of these maps from
   production (filtered by both id and map_type) AND COPY every Map row
   over, in a single transaction. Other readers see either the
   pre-DELETE state or the post-COPY state, never the half-empty middle.
2. Phase 2 (chunked): COPY the detail rows (geodata_zone or geodata_line)
   over in id-keyset pages so the production database doesn't have to
   absorb the whole batch in one transaction. Each chunk commits
   independently — readers querying detail rows see partial data for the
   affected maps until the loop finishes. This is the deliberate
   tradeoff for being able to transfer multi-million-row datasets.
3. Phase 3: Reset the auto-increment sequences on production so future
   inserts don't collide with imported ids.

Prerequisites
-------------
1. Local database must be the active Django connection (DATABASE_URL).
2. Production database must be reachable via PROD_DATABASE_URL,
   typically through a Scalingo db-tunnel:

       scalingo --app envergo db-tunnel SCALINGO_POSTGRESQL_URL
       export PROD_DATABASE_URL="postgres://user:pass@127.0.0.1:10000/dbname"

Usage
-----
By default the command runs in dry-run mode: every safety check executes,
the destination database and the planned action are printed, and then the
command exits without writing anything.

    python manage.py copy_geometries_to_prod --map-type terres_emergees

When you have verified the dry-run output, re-run with --apply to actually
perform the destructive operation. You will still be asked to type a
confirmation phrase before any DELETE or COPY happens.

    python manage.py copy_geometries_to_prod --map-type terres_emergees --apply

To resume after a failure, pass the last successfully transferred id (the
script prints it on every chunk). --apply is still required:

    python manage.py copy_geometries_to_prod --map-type terres_emergees --apply --after-id 1234567
"""

import argparse
import os
import sys
from dataclasses import dataclass
from logging import getLogger
from typing import NamedTuple

import psycopg
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from envergo.geodata.management.helpers import (
    VALID_MAP_TYPES,
    refuse_production_settings,
)
from envergo.geodata.models import Map

logger = getLogger(__name__)


# Allow-list of table names this command may interpolate into raw SQL.
# Defense in depth — every method that touches `table` re-checks via
# assert_table_safe() before any string interpolation.
ALLOWED_DETAIL_TABLES = ("geodata_zone", "geodata_line")


class DbIdentity(NamedTuple):
    """Server-side identity of a Postgres connection.

    Used to compare two connections for equality (the local-vs-prod safety
    check) and to display the destination database in confirmation prompts.
    Subclassing NamedTuple keeps every existing tuple operation working
    (equality, indexing, unpacking) while adding attribute access so
    consumers can read `identity.dbname` instead of destructuring by
    position.
    """

    host: str
    port: str
    dbname: str


class ColumnSchema(NamedTuple):
    """Schema metadata for one column.

    Used by verify_schemas_match to compare column name, type, AND
    nullability across local and prod, so a type-only or nullability-only
    migration drift can't slip past the check.
    """

    name: str
    data_type: str
    is_nullable: str


@dataclass(frozen=True)
class CopyPlan:
    """Everything the warning banner and typed confirmation need to render.

    Computed once after every safety check passes; passed to presentation
    methods so the banner, the dry-run summary, and the typed confirmation
    can never disagree on what was decided.
    """

    map_type: str
    table: str
    after_id: int
    local_id: DbIdentity
    prod_id: DbIdentity
    nb_maps_to_insert: int  # in local but not yet in prod
    nb_maps_to_replace: int  # in both — prod copy will be overwritten
    nb_maps_skipped: int  # local maps with import_status != 'success'
    nb_detail_rows: int  # for resume, only the rows still to copy

    @property
    def is_resume(self):
        return self.after_id > 0


def assert_table_safe(table):
    """Reject any table name not on the allow-list before SQL interpolation."""
    if table not in ALLOWED_DETAIL_TABLES:
        raise CommandError(
            f"Refusing to operate on unknown table {table!r}. "
            f"Allowed: {ALLOWED_DETAIL_TABLES}"
        )


def positive_int(value):
    """argparse type validator: accept only integers >= 1.

    Wraps the int() call so non-numeric input ('abc', '1.5', '') produces
    a consistent custom error message instead of the generic ValueError
    that argparse would otherwise re-render.
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"must be a positive integer, got {value!r}"
        )
    if n < 1:
        raise argparse.ArgumentTypeError(
            f"must be a positive integer, got {n}"
        )
    return n


def non_negative_int(value):
    """argparse type validator: accept only integers >= 0.

    Wraps the int() call so non-numeric input ('abc', '1.5', '') produces
    a consistent custom error message instead of the generic ValueError
    that argparse would otherwise re-render.
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"must be a non-negative integer, got {value!r}"
        )
    if n < 0:
        raise argparse.ArgumentTypeError(
            f"must be a non-negative integer, got {n}"
        )
    return n


def open_local_connection():
    """Open a raw, READ-ONLY psycopg connection to the local database.

    We use a separate raw connection rather than `django.db.connection`
    for two reasons:

    1. We mark this connection read-only as defense in depth (line below).
       Setting `read_only = True` on Django's shared connection would
       poison every subsequent ORM call in the same process.

    2. We commit between chunks in the COPY phases. Doing that on
       Django's shared connection would mess with its transaction state
       and surprise any later ORM call in the same process.

    Bonus: the prod connection has to come from PROD_DATABASE_URL anyway,
    so using raw psycopg on both ends keeps the COPY pipe symmetric.
    """
    db = settings.DATABASES["default"]
    conn = psycopg.connect(
        host=db["HOST"] or None,
        port=db["PORT"] or None,
        dbname=db["NAME"],
        user=db["USER"] or None,
        password=db["PASSWORD"] or None,
    )
    conn.read_only = True
    return conn


def open_prod_connection():
    """Open a raw psycopg connection to the production database.

    Connection string is read from the PROD_DATABASE_URL env var so the
    command stays usable from a developer machine without touching
    settings.DATABASES (production credentials never live in Django
    settings on dev).
    """
    url = os.environ.get("PROD_DATABASE_URL")
    if not url:
        raise CommandError(
            "PROD_DATABASE_URL environment variable is required. "
            "See the docstring of this command for tunnel setup instructions."
        )
    return psycopg.connect(url)


def query_connection_identity(conn):
    """Return a stable DbIdentity for a connection.

    The values come from the server itself rather than the connection
    string, so two strings that resolve to the same physical database
    (e.g. 'localhost' vs '127.0.0.1') produce the same identity. The
    fallback for Unix-socket connections uses sentinel strings so the
    comparison is still meaningful.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_database(), "
            "       coalesce(inet_server_addr()::text, 'local-socket'), "
            "       coalesce(inet_server_port()::text, '0')"
        )
        dbname, host, port = cur.fetchone()
    return DbIdentity(host=host, port=port, dbname=dbname)


def format_db_identity(identity):
    """Pretty-print a DbIdentity for human eyes."""
    return f"{identity.dbname} @ {identity.host}:{identity.port}"


def get_table_columns(conn, table_name):
    """Return the ordered list of column names for a public-schema table.

    Raises CommandError if the table is not found in `public`. An empty
    column list would otherwise compare equal across local and prod in
    verify_schemas_match and let an unknown table slip past the check.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            [table_name],
        )
        columns = [row[0] for row in cur.fetchall()]
    if not columns:
        raise CommandError(
            f"Table 'public.{table_name}' not found. Refusing to operate "
            f"on a table I cannot introspect."
        )
    return columns


def get_table_schema(conn, table_name):
    """Return ColumnSchema entries (name, type, nullable) for a public table.

    Raises CommandError if the table is not found, for the same reason
    as get_table_columns.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            [table_name],
        )
        schema = [ColumnSchema(*row) for row in cur.fetchall()]
    if not schema:
        raise CommandError(
            f"Table 'public.{table_name}' not found. Refusing to operate "
            f"on a table I cannot introspect."
        )
    return schema


def diff_schemas(local_schema, prod_schema):
    """Return a human-readable diff of two schemas, or None if equivalent.

    Compares columns by NAME, not by ordinal position. Two databases
    that have the same logical schema can sit on disk with different
    physical column orders if their migration history differs (e.g.
    prod was built incrementally while local was built from squashed
    migrations). PostgreSQL never reorders columns after the fact, but
    that's harmless for this command: our COPY statements use an
    explicit column list, so the table's physical order is irrelevant.

    Two schemas are equivalent for our purposes iff:
      - They have the same set of column names.
      - Every shared column has the same data_type and is_nullable.

    Returns None when equivalent. Otherwise returns a diff string ready
    to be embedded in an error message.
    """
    local_by_name = {col.name: col for col in local_schema}
    prod_by_name = {col.name: col for col in prod_schema}

    if local_by_name == prod_by_name:
        return None

    diffs = []

    only_local = sorted(set(local_by_name) - set(prod_by_name))
    only_prod = sorted(set(prod_by_name) - set(local_by_name))
    if only_local:
        diffs.append(f"  columns only on local: {only_local}")
    if only_prod:
        diffs.append(f"  columns only on prod:  {only_prod}")

    for name in sorted(set(local_by_name) & set(prod_by_name)):
        l_col = local_by_name[name]
        p_col = prod_by_name[name]
        if l_col != p_col:
            diffs.append(
                f"  {name!r}: "
                f"local=(type={l_col.data_type}, nullable={l_col.is_nullable}) "
                f"prod=(type={p_col.data_type}, nullable={p_col.is_nullable})"
            )

    return "\n".join(diffs)


def verify_schemas_match(local, prod, table_names):
    """Refuse to copy when local and prod have diverging schemas.

    See diff_schemas for the equivalence rule (compares by name, type,
    and nullability — not by physical column order). A migration applied
    on one side but not the other (column added or dropped, type change,
    nullability change) is caught here. Once verified, the COPY queries
    use an explicit column list, so the table's natural ordinal position
    doesn't need to match.
    """
    for table_name in table_names:
        local_schema = get_table_schema(local, table_name)
        prod_schema = get_table_schema(prod, table_name)
        diff = diff_schemas(local_schema, prod_schema)
        if diff is None:
            continue
        raise CommandError(
            f"Schema drift detected on {table_name}:\n"
            + diff
            + "\nRun pending migrations on the lagging side before retrying."
        )


def detect_geometry_table(local_conn, map_ids):
    """Return ('geodata_zone'|'geodata_line', row_count) for the given maps.

    Polygon maps store their geometries in `geodata_zone`, line maps in
    `geodata_line`. We detect which one by counting rows in each table for
    the selected map ids. A batch that has rows in both tables is treated
    as an error: the upstream import pipeline (`process_map`) only ever
    writes to one of the two per file, so a mix indicates a data
    inconsistency that the operator should investigate before pushing to
    production.
    """
    with local_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM geodata_zone WHERE map_id = ANY(%s)",
            [map_ids],
        )
        nb_zones = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM geodata_line WHERE map_id = ANY(%s)",
            [map_ids],
        )
        nb_lines = cur.fetchone()[0]

    if nb_zones and nb_lines:
        raise CommandError(
            f"Mixed geometry types for the selected maps "
            f"({nb_zones} zones, {nb_lines} lines). "
            f"copy_geometries_to_prod expects every selected map to use a "
            f"single detail table."
        )
    if not nb_zones and not nb_lines:
        raise CommandError(
            "Selected maps have no zones and no lines. "
            "Did the local processing finish successfully?"
        )
    return ("geodata_zone", nb_zones) if nb_zones else ("geodata_line", nb_lines)


def check_no_id_collisions(prod, map_ids, map_type):
    """Abort if any prod row has an id we'll touch but a different map_type.

    The destructive phase deletes prod Maps by id, then COPY-inserts the
    local Maps with their original ids. If a prod Map exists with one of
    those ids but belongs to a different map_type, the operator's local
    DB is NOT a fresh dump of prod — somebody created new rows in prod
    after the dump was taken. Continuing would either:

      - Destroy unrelated production data (the DELETE would catch the
        wrong row), or
      - Cause a primary-key collision on COPY (after we filter the DELETE
        by map_type to avoid the first failure mode).

    Either outcome means the operator's assumption is wrong and the
    operation must be aborted.

    The geodata_map.map_type column is currently NOT NULL at the database
    level, so empty string is the only "untyped" value that exists in
    practice (and `'' IS DISTINCT FROM 'foo'` is True, so empty-type rows
    are correctly flagged). `IS DISTINCT FROM` is used instead of `!=` as
    defense in depth: if a future migration ever drops the NOT NULL
    constraint, hypothetical NULL rows would still be caught here, where
    plain `!=` would silently let them through (`NULL != 'foo'` evaluates
    to NULL and the row would be filtered out by the WHERE clause).
    """
    with prod.cursor() as cur:
        cur.execute(
            "SELECT id, map_type, name FROM geodata_map "
            "WHERE id = ANY(%s) AND map_type IS DISTINCT FROM %s "
            "ORDER BY id LIMIT 10",
            [map_ids, map_type],
        )
        sample = cur.fetchall()
        if not sample:
            return
        cur.execute(
            "SELECT COUNT(*) FROM geodata_map "
            "WHERE id = ANY(%s) AND map_type IS DISTINCT FROM %s",
            [map_ids, map_type],
        )
        total = cur.fetchone()[0]

    sample_lines = "\n  ".join(
        f"id={row[0]} map_type={row[1]!r} name={row[2]!r}" for row in sample
    )
    raise CommandError(
        f"Id collision detected: {total} prod Maps have ids that overlap "
        f"with the local {map_type!r} batch but belong to a different "
        f"map_type. Sample:\n  {sample_lines}\n"
        f"This usually means the local DB was NOT imported against a fresh "
        f"prod dump. Re-import locally against a fresh dump and retry."
    )


def collect_local_map_ids(map_type):
    """Return (eligible_map_ids, nb_skipped) for the local database.

    Only Maps with import_status='success' are eligible: failed, partial,
    or never-processed maps would propagate broken or empty data to
    production. The count of skipped maps is returned so the warning
    banner can surface them to the operator — silently dropping them
    would be confusing.
    """
    base_qs = Map.objects.filter(map_type=map_type)
    nb_total = base_qs.count()
    eligible_qs = base_qs.filter(import_status="success").order_by("id")
    map_ids = list(eligible_qs.values_list("id", flat=True))
    nb_skipped = nb_total - len(map_ids)
    return map_ids, nb_skipped


def count_existing_prod_maps(prod, map_ids, map_type):
    """Count prod Maps that already exist with our id and map_type.

    These rows will be REPLACED by Phase 1 (DELETE then COPY). Reporting
    the count separately from the new-map count gives the operator a
    clear picture of how much existing data they're about to overwrite.
    """
    with prod.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM geodata_map "
            "WHERE id = ANY(%s) AND map_type = %s",
            [map_ids, map_type],
        )
        return cur.fetchone()[0]


def count_pending_detail_rows(local, table, map_ids, after_id):
    """Count detail rows on local that still need to be transferred.

    For a fresh run (after_id == 0) this returns the total. For a resume
    run, it returns only the rows above after_id, so the warning banner
    shows the operator how much work actually remains.
    """
    assert_table_safe(table)
    with local.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE id > %s AND map_id = ANY(%s)",
            [after_id, map_ids],
        )
        return cur.fetchone()[0]


class Command(BaseCommand):
    help = (
        "Copy Maps and their Zones/Lines from the local database to "
        "production. DESTRUCTIVE — see the module docstring for safety "
        "requirements."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--map-type",
            required=True,
            choices=sorted(VALID_MAP_TYPES),
            help="Only copy Maps of this type",
        )
        parser.add_argument(
            "--page-size",
            type=positive_int,
            default=5000,
            help="Number of detail rows per COPY chunk (default: 5000)",
        )
        parser.add_argument(
            "--after-id",
            type=non_negative_int,
            default=0,
            help="Resume after this detail-row id. When set, the Maps phase "
            "is skipped (Maps were already copied on the first run).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="REQUIRED to actually perform the destructive operation. "
            "Without this flag the command runs in dry-run mode: every "
            "safety check executes and the planned action is printed, but "
            "no DELETE or COPY happens. Even with --apply, the operator "
            "must still type the confirmation phrase before any write.",
        )

    def handle(self, *args, **options):
        """Run every safety check, build the plan, then execute the three phases.

        The destructive path is gated by FIVE independent guards, all of
        which must pass before the operator is even shown the typed
        confirmation:

          1. DJANGO_SETTINGS_MODULE must not contain 'production'.
          2. Local and prod must resolve to different physical databases
             (server-side identity comparison, robust to alias differences).
          3. Local must have at least one successfully-imported map of
             the requested type. Failed/pending imports are excluded.
          4. Local and prod schemas must match column-by-name (with type
             and nullability verification).
          5. No prod row may have an id in the local batch with a
             different map_type (would mean local is not a fresh dump).

        After the guards pass, a CopyPlan is computed once and passed to
        the warning banner, the dry-run summary, and the typed
        confirmation prompt — they can never disagree on what was decided.

        Without --apply the command exits cleanly after the banner. With
        --apply, the operator must still type a confirmation phrase
        before any DELETE or COPY happens. Then the three phases run:
        Phase 1 (atomic DELETE+COPY of Maps), Phase 2 (chunked detail
        copy with per-chunk commits), Phase 3 (sequence reset).
        """
        map_type = options["map_type"]
        page_size = options["page_size"]
        after_id = options["after_id"]
        apply_changes = options["apply"]

        # Guard 1: cheap early exit. Robust check is the local-vs-prod
        # identity comparison once both connections are open.
        refuse_production_settings()

        with open_local_connection() as local, open_prod_connection() as prod:
            # ── Guard 2: local and prod must resolve to different DBs ──
            # The identities come from server-side queries, so two
            # different connection strings that physically point at the
            # same cluster (e.g. localhost vs 127.0.0.1) still compare
            # equal here.
            local_id = query_connection_identity(local)
            prod_id = query_connection_identity(prod)
            if local_id == prod_id:
                raise CommandError(
                    f"Local and PROD connections resolve to the SAME "
                    f"database ({format_db_identity(local_id)}). "
                    f"Refusing to run."
                )

            # ── Guard 3: collect map ids (only successfully imported) ──
            map_ids, nb_skipped = collect_local_map_ids(map_type)
            if not map_ids:
                self.stdout.write(
                    f"No successfully imported maps of type {map_type!r} "
                    f"in local database "
                    f"({format_db_identity(local_id)}). Nothing to do."
                )
                if nb_skipped > 0:
                    self.stdout.write(
                        f"  ({nb_skipped} local maps were skipped because "
                        f"their import_status is not 'success'.)"
                    )
                return

            self.stdout.write(
                f"Found {len(map_ids)} successfully imported maps of type "
                f"{map_type!r} in {format_db_identity(local_id)}."
            )

            table, _ = detect_geometry_table(local, map_ids)
            assert_table_safe(table)

            # ── Guard 4: schemas must match (names, types, nullability) ─
            verify_schemas_match(local, prod, ("geodata_map", table))
            map_columns = get_table_columns(local, "geodata_map")
            detail_columns = get_table_columns(local, table)

            # ── Guard 5: id collision check against prod ──────────────
            check_no_id_collisions(prod, map_ids, map_type)

            # ── Compute the plan once for the banner and confirmation ──
            nb_existing = count_existing_prod_maps(prod, map_ids, map_type)
            nb_pending_rows = count_pending_detail_rows(
                local, table, map_ids, after_id
            )
            plan = CopyPlan(
                map_type=map_type,
                table=table,
                after_id=after_id,
                local_id=local_id,
                prod_id=prod_id,
                nb_maps_to_insert=len(map_ids) - nb_existing,
                nb_maps_to_replace=nb_existing,
                nb_maps_skipped=nb_skipped,
                nb_detail_rows=nb_pending_rows,
            )

            # ── Big red warning ────────────────────────────────────────
            self.print_warning_banner(plan)

            # ── Default-safe exit ──────────────────────────────────────
            # The destructive path requires --apply *and* the typed
            # confirmation below. Without --apply we exit cleanly here
            # so a fat-fingered run defaults to safe.
            if not apply_changes:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Dry run — every safety check passed. No changes made."
                    )
                )
                self.stdout.write(
                    "Re-run with --apply to perform the destructive operation."
                )
                return

            # ── Typed confirmation (always required, even on resume) ──
            self.require_typed_confirmation(plan)

            # ── Phase 1: cleanup + Maps ────────────────────────────────
            if after_id == 0:
                self.cleanup_and_copy_maps(
                    local, prod, map_ids, table, map_columns, map_type
                )
            else:
                self.stdout.write(
                    f">>> Phase 1: skipped (resuming after id {after_id})"
                )

            # ── Phase 2: paginated detail copy ────────────────────────
            last_id = self.copy_detail_rows(
                local, prod, map_ids, table, detail_columns,
                page_size, after_id, map_type,
            )

            # ── Phase 3: reset sequences on production ────────────────
            self.reset_sequences(prod, table)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {table} rows copied up to id {last_id}."
            )
        )

    def print_warning_banner(self, plan):
        """Print a hard-to-miss warning describing exactly what will happen."""
        if plan.is_resume:
            action_lines = [
                f"  RESUME COPY of {plan.map_type!r} after id {plan.after_id}",
                f"  (no DELETE — Phase 1 was completed in a previous run)",
                f"  - {plan.nb_detail_rows} {plan.table} rows still to transfer",
            ]
        else:
            action_lines = [
                f"  - {plan.nb_maps_to_insert} new {plan.map_type!r} maps "
                f"will be INSERTED in prod",
                f"  - {plan.nb_maps_to_replace} existing prod {plan.map_type!r} "
                f"maps will be OVERWRITTEN",
                f"  - {plan.nb_detail_rows} {plan.table} rows will be transferred",
            ]
            if plan.nb_maps_skipped > 0:
                action_lines.append(
                    f"  - {plan.nb_maps_skipped} local maps SKIPPED "
                    f"(import_status != 'success')"
                )

        action_block = "\n".join(action_lines)

        banner = (
            "\n"
            "═══════════════════════════════════════════════════════════════════════\n"
            "  ⚠  DESTRUCTIVE PRODUCTION OPERATION — READ EVERY LINE BEFORE PROCEEDING  ⚠\n"
            "═══════════════════════════════════════════════════════════════════════\n"
            "\n"
            "This command DELETES rows from a production database and replaces them\n"
            "with rows from a local database. It is ONLY safe to run if ALL of the\n"
            "following are true:\n"
            "\n"
            "  1. The local DB was JUST imported against a FRESH dump of production.\n"
            "     Stale dumps cause id collisions and silent destruction of unrelated\n"
            "     production data.\n"
            "\n"
            "  2. Map creation has been BLOCKED on production for the entire duration\n"
            "     of this run (no admin uploads, no API ingest, no Celery jobs that\n"
            "     create Maps). Any new prod row created after the dump was taken\n"
            "     would either be destroyed or cause a primary-key collision.\n"
            "\n"
            "  3. You have verified BOTH connection targets below. The 'PROD' target\n"
            "     is what will be modified — make sure it is the correct cluster.\n"
            "\n"
            f"     Source (LOCAL, read-only) : {format_db_identity(plan.local_id)}\n"
            f"     Target (PROD,  will mutate) : {format_db_identity(plan.prod_id)}\n"
            "\n"
            "  Planned action:\n"
            f"{action_block}\n"
            "\n"
            "  Cascading deletes: removing a Map row also removes every row in\n"
            "  geodata_zone, geodata_line, hedges_speciesmap, and any other table\n"
            "  whose foreign key declares ON DELETE CASCADE. Verify that no prod\n"
            "  data outside the targeted map_type depends on these maps.\n"
            "\n"
            "═══════════════════════════════════════════════════════════════════════\n"
        )
        self.stdout.write(self.style.ERROR(banner))

    def require_typed_confirmation(self, plan):
        """Require the operator to type a unique phrase before proceeding.

        The phrase embeds the map_type and the prod database name, so a
        wrong-terminal mistake (different env vars) produces a different
        phrase and the operator can't accidentally confirm by muscle memory.
        """
        verb = "resume" if plan.is_resume else "replace"
        phrase = f"{verb} {plan.map_type} in {plan.prod_id.dbname}"

        self.stdout.write(
            "\nTo proceed, type the phrase below EXACTLY (no quotes) and "
            "press Enter.\nAnything else cancels the operation."
        )
        self.stdout.write(self.style.NOTICE(f"  Required phrase: {phrase}"))
        try:
            typed = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            self.stdout.write(self.style.ERROR("\nCancelled."))
            sys.exit(1)
        if typed != phrase:
            self.stdout.write(self.style.ERROR("Cancelled (phrase mismatch)."))
            sys.exit(1)

    def cleanup_and_copy_maps(
        self, local, prod, map_ids, table, map_columns, map_type
    ):
        """Delete previous prod rows for these maps, then COPY Maps over.

        Atomic: the DELETEs and the COPY share a single transaction.
        We do NOT commit between them. Other readers of prod (the live
        application) see either the pre-DELETE state or the post-COPY
        state, never the half-empty middle. PostgreSQL's MVCC handles
        the visibility — no extra locking needed.

        Both DELETEs are scoped by (id, map_type) so an id collision
        with a different map_type can never destroy unrelated production
        data — that case is already caught by check_no_id_collisions,
        but the belt-and-braces filter on the DELETE itself is the
        actual safety net. The COPY SELECT is also scoped by map_type
        for the same reason.

        Detail rows are deleted before Maps because of the FK constraint.
        On a fresh first run both DELETEs are no-ops.
        """
        assert_table_safe(table)
        self.stdout.write(
            ">>> Phase 1: cleaning up previous import and transferring Maps "
            "(atomic)"
        )
        with prod.cursor() as prod_cur:
            prod_cur.execute(
                f"DELETE FROM {table} WHERE map_id IN ("
                f"  SELECT id FROM geodata_map "
                f"  WHERE id = ANY(%s) AND map_type = %s"
                f")",
                [map_ids, map_type],
            )
            prod_cur.execute(
                "DELETE FROM geodata_map "
                "WHERE id = ANY(%s) AND map_type = %s",
                [map_ids, map_type],
            )
        # Intentionally NO commit here — the DELETE and the COPY below
        # must commit together so the half-empty state is never visible
        # to other readers.

        columns_csv = ", ".join(map_columns)
        with prod.cursor() as prod_cur:
            with prod_cur.copy(
                f"COPY geodata_map ({columns_csv}) FROM STDIN"
            ) as copy_in:
                with local.cursor() as local_cur:
                    with local_cur.copy(
                        f"COPY (SELECT {columns_csv} FROM geodata_map "
                        f"  WHERE id = ANY(%s) AND map_type = %s "
                        f"  ORDER BY id) TO STDOUT",
                        [map_ids, map_type],
                    ) as copy_out:
                        for chunk in copy_out:
                            copy_in.write(chunk)
        prod.commit()
        self.stdout.write(
            f"  Phase 1 done: {len(map_ids)} maps replaced atomically."
        )

    def copy_detail_rows(
        self, local, prod, map_ids, table, detail_columns,
        page_size, after_id, map_type,
    ):
        """Stream detail rows local → prod in keyset-paginated chunks.

        Pagination is by id, not OFFSET, so the cost stays constant as
        the loop progresses (OFFSET would scan and skip earlier rows on
        every page, which gets expensive on large tables).

        Each chunk commits independently. Readers querying detail rows
        during Phase 2 see partial data for the affected maps until the
        loop finishes — this is the deliberate tradeoff for being able
        to transfer multi-million-row datasets without holding a single
        huge transaction.

        The COPY SELECT joins through geodata_map filtered by map_type,
        so neither column drift nor stale map_ids can move the wrong
        rows. The destination COPY uses the explicit column list locked
        in by verify_schemas_match.
        """
        assert_table_safe(table)
        self.stdout.write(
            f">>> Phase 2: transferring {table} (page_size={page_size})"
        )
        last_id = after_id
        chunks_run = 0
        rows_transferred = 0
        columns_csv = ", ".join(detail_columns)
        prefixed_columns = ", ".join(f"d.{c}" for c in detail_columns)

        while True:
            with local.cursor() as cur:
                # MAX(id) and COUNT(*) of the next page in one query, so
                # the chunk announcement reflects the actual row count.
                cur.execute(
                    f"SELECT MAX(id), COUNT(*) FROM ("
                    f"  SELECT id FROM {table} "
                    f"  WHERE id > %s AND map_id = ANY(%s) "
                    f"  ORDER BY id LIMIT %s"
                    f") sub",
                    [last_id, map_ids, page_size],
                )
                next_max, chunk_count = cur.fetchone()
            if next_max is None:
                break

            chunks_run += 1
            self.stdout.write(
                f"  chunk {chunks_run}: {chunk_count} rows "
                f"(ids in ({last_id}, {next_max}])"
            )

            with prod.cursor() as prod_cur:
                with prod_cur.copy(
                    f"COPY {table} ({columns_csv}) FROM STDIN"
                ) as copy_in:
                    with local.cursor() as local_cur:
                        with local_cur.copy(
                            f"COPY (SELECT {prefixed_columns} "
                            f"  FROM {table} d "
                            f"  JOIN geodata_map m ON m.id = d.map_id "
                            f"  WHERE d.id > %s AND d.id <= %s "
                            f"    AND d.map_id = ANY(%s) "
                            f"    AND m.map_type = %s "
                            f"  ORDER BY d.id) TO STDOUT",
                            [last_id, next_max, map_ids, map_type],
                        ) as copy_out:
                            for buf in copy_out:
                                copy_in.write(buf)
            prod.commit()
            rows_transferred += chunk_count
            last_id = next_max

        if chunks_run == 0:
            if after_id > 0:
                self.stdout.write(self.style.WARNING(
                    f"  No rows found above id {after_id}. Either Phase 2 "
                    f"is already complete or --after-id is wrong."
                ))
            else:
                self.stdout.write("  No detail rows found to transfer.")
        else:
            self.stdout.write(
                f"  Phase 2 done: {rows_transferred} rows in "
                f"{chunks_run} chunks."
            )

        return last_id

    def reset_sequences(self, prod, table):
        """Advance the prod sequences past the largest imported id.

        COPY inserts rows with explicit ids but does not advance
        PostgreSQL auto-increment sequences. Without this step the next
        Django-created Map or detail row would collide with imported ids.

        COALESCE handles the empty-table edge case: setval(seq, NULL)
        raises an error.
        """
        assert_table_safe(table)
        self.stdout.write(">>> Phase 3: resetting primary key sequences")
        with prod.cursor() as prod_cur:
            prod_cur.execute(
                "SELECT setval(pg_get_serial_sequence('geodata_map', 'id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM geodata_map))"
            )
            prod_cur.execute(
                f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                f"(SELECT COALESCE(MAX(id), 1) FROM {table}))",
                [table],
            )
        prod.commit()
