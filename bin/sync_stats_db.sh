#!/bin/bash
# Nightly sync of the production database into the anonymized copy queried by
# Metabase (envergo-stats app). Runs as a Scalingo scheduled task on the
# envergo app.
#
# Safety model: no command in this script holds a credential that can write
# to production. Both assertions below enforce it at runtime.

set -euo pipefail

# Required environment:
# - SYNC_SOURCE_URL: production database, as a READ-ONLY user (dump source).
# - SYNC_TARGET_URL: stats database, as its owner (restore/anonymize target).
#   This user does not exist on the production cluster.
# - SYNC_TARGET_DB_NAME: name of the stats database, to verify we restore
#   into the intended place.
: "${SYNC_SOURCE_URL:?SYNC_SOURCE_URL is not set}"
: "${SYNC_TARGET_URL:?SYNC_TARGET_URL is not set}"
: "${SYNC_TARGET_DB_NAME:?SYNC_TARGET_DB_NAME is not set}"

# Client 17: needed for --exclude-extension, and matches the target server.
dbclient-fetcher psql 17
export PSQL_BIN="$HOME/bin/psql"

# Fail fast if SYNC_SOURCE_URL is ever misconfigured with a writable user.
# has_table_privilege is true if ANY of the listed privileges is held.
# psql -tA: print the bare value, no headers or padding.
source_can_write=$("$PSQL_BIN" "$SYNC_SOURCE_URL" -tA -c \
    "SELECT has_table_privilege(current_user, 'users_user', 'INSERT, UPDATE, DELETE, TRUNCATE')")
if [ "$source_can_write" != "f" ]; then
    echo "SYNC_SOURCE_URL user has write access on production, aborting." >&2
    exit 1
fi

# A mispasted SYNC_TARGET_URL fails here, before anything is written.
actual_db_name=$("$PSQL_BIN" "$SYNC_TARGET_URL" -tA -c "SELECT current_database()")
if [ "$actual_db_name" != "$SYNC_TARGET_DB_NAME" ]; then
    echo "Connected to database '$actual_db_name' but expected '$SYNC_TARGET_DB_NAME', aborting." >&2
    exit 1
fi

PG_OPTIONS=(
    --clean
    --if-exists
    --no-owner
    --no-privileges
    --no-comments
)

# Same exclusions as review apps (bin/first_deploy.sh), plus the postgis
# extension itself: it pre-exists on the target.
PG_EXCLUDE=(
    -N information_schema
    -N '^pg_*'
    --exclude-extension=postgis
    --exclude-table=spatial_ref_sys
    --exclude-table-data=geodata_map
    --exclude-table-data=geodata_zone
    --exclude-table-data=evaluations_recipientstatus
    --exclude-table-data=geodata_catchmentareatile
)

# Stream dump into restore: scheduled task containers offer little memory and
# disk, so the dump must never be materialized. Sequential (non-parallel)
# restore is the price; the nightly schedule can afford it.
echo "Syncing production data to the stats database..."
"$HOME/bin/pg_dump" "${PG_OPTIONS[@]}" "${PG_EXCLUDE[@]}" --format c --dbname "$SYNC_SOURCE_URL" \
    | "$HOME/bin/pg_restore" "${PG_OPTIONS[@]}" --dbname "$SYNC_TARGET_URL"

bash "$HOME/bin/anonymize_db.sh" "$SYNC_TARGET_URL"

# Grant access to the newly created tables to the metabase ro user
echo "Granting read access to metabase_ro..."

# Fetch the list of prod db table names
restored_tables=$("$PSQL_BIN" "$SYNC_SOURCE_URL" -tA -c \
    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'spatial_ref_sys'")

# Run the "grant access" queries
for table in $restored_tables; do
    "$PSQL_BIN" "$SYNC_TARGET_URL" --quiet --set ON_ERROR_STOP=1 \
        -c "GRANT SELECT ON public.\"$table\" TO metabase_ro;"
done

echo "Stats database sync complete."
