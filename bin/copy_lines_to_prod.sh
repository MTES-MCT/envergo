#!/bin/bash
#
# Transfer geodata_line rows and their associated geodata_map rows from a
# local database to the production database.
#
# Unlike copy_polygons.sh (which runs inside a Scalingo one-off container to
# replicate data between production and staging), this script runs from a
# developer machine to push large datasets (e.g. BD Haie — ~20M hedges) into
# production. Direct COPY via pg_dump is not feasible because the production
# DB cannot absorb the entire dataset in a single transaction. Instead, we
# page the transfer into small chunks.
#
# Prerequisites
# =============
#
# 1. Prepare the local database
#
#    Import the data locally against a fresh copy of the production database so
#    that primary keys are guaranteed not to collide with existing production
#    rows. Block Map/Line creation in production while the transfer runs.
#
# 2. Open a tunnel to the production database
#
#    Run the following command in a separate terminal:
#
#        scalingo --app envergo db-tunnel SCALINGO_POSTGRESQL_URL
#
#    It will print something like:
#
#        Building tunnel to <host>:<port>
#        You can access your database on:
#        127.0.0.1:10000
#
#    Use the displayed host, port, and credentials to build PROD_DB below.
#
# 3. Set the environment variables
#
#    LOCAL_DB: connection string to the local database. Typically found in
#    your .env file as DATABASE_URL, e.g.:
#
#        export LOCAL_DB="postgres://user:password@localhost:5432/envergo"
#
#    PROD_DB: connection string through the Scalingo tunnel, built from the
#    credentials printed by `scalingo db-tunnel`, e.g.:
#
#        export PROD_DB="postgres://user:password@127.0.0.1:10000/dbname"
#
# Usage
# =====
#
#    LOCAL_DB="..." PROD_DB="..." bash bin/copy_lines_to_prod.sh
#
# To resume after a failure, set AFTER_ID to the last successfully transferred
# Line id (shown in the script output):
#
#    LOCAL_DB="..." PROD_DB="..." AFTER_ID=5000000 bash bin/copy_lines_to_prod.sh
#
# When resuming, Maps are skipped (they were already transferred in the first
# run). If Maps also need re-transferring, set AFTER_ID=0 explicitly.
#
# Tuning: PAGE_SIZE defaults to 5000. Increase for speed, decrease if the
# production DB struggles:
#
#    LOCAL_DB="..." PROD_DB="..." PAGE_SIZE=10000 bash bin/copy_lines_to_prod.sh
#
# Starting from scratch
# =====================
#
# The script is safe to re-run. When AFTER_ID is not set, it deletes any
# previously imported Lines and Maps from production (identified by the Map
# IDs from the local database) before transferring again.

set -euo pipefail

PAGE_SIZE=${PAGE_SIZE:-5000}
AFTER_ID=${AFTER_ID:-}

if [ -z "${LOCAL_DB:-}" ] || [ -z "${PROD_DB:-}" ]; then
    echo "Error: LOCAL_DB and PROD_DB environment variables are required."
    echo "See the header of this script for usage instructions."
    exit 1
fi

# ── Phase 0: Collect Map IDs to transfer ─────────────────────────────

map_ids=$(psql "$LOCAL_DB" -t -A -c "
    SELECT DISTINCT map_id FROM geodata_line ORDER BY map_id;
")

if [ -z "$map_ids" ]; then
    echo "No Lines found in local database. Nothing to transfer."
    exit 0
fi

map_ids_csv=$(echo "$map_ids" | paste -sd,)

echo "  Map IDs to transfer: $map_ids_csv"

# ── Phase 1: Cleanup + Transfer Maps ────────────────────────────────

if [ -z "$AFTER_ID" ]; then
    echo ">>> Phase 1: Cleaning up previous import (if any) and transferring Maps"

    # Delete Lines referencing these Maps, then the Maps themselves.
    # Lines must be deleted first (FK constraint). If this is the first run,
    # the DELETEs are no-ops.
    psql "$PROD_DB" -c "DELETE FROM geodata_line WHERE map_id IN ($map_ids_csv);"
    psql "$PROD_DB" -c "DELETE FROM geodata_map WHERE id IN ($map_ids_csv);"

    echo "  Previous data cleaned up."

    nb_maps=$(echo "$map_ids" | wc -l)
    echo "  $nb_maps maps to transfer"

    psql "$LOCAL_DB" -c "
        COPY (
            SELECT *
            FROM geodata_map
            WHERE id IN (SELECT DISTINCT map_id FROM geodata_line)
            ORDER BY id
        ) TO stdout
    " | psql "$PROD_DB" -c "COPY geodata_map FROM stdin;"

    echo "  Maps transferred."

    AFTER_ID=0
else
    echo ">>> Phase 1: Skipped (resuming after id $AFTER_ID)"
fi

# ── Phase 2: Transfer Lines (paginated with keyset pagination) ──────

echo ">>> Phase 2: Transferring Lines"

nb_lines=$(psql "$LOCAL_DB" -t -A -c "SELECT COUNT(*) FROM geodata_line;")
echo "  $nb_lines total lines in local database"

last_id=$AFTER_ID
chunk=0

while true; do
    chunk=$((chunk + 1))

    # Fetch a page of rows with id > last_id and capture the max id returned.
    # COPY itself doesn't return values, so we run a separate query to get
    # the upper bound of this chunk first.
    next_max_id=$(psql "$LOCAL_DB" -t -A -c "
        SELECT MAX(id) FROM (
            SELECT id FROM geodata_line
            WHERE id > $last_id
            ORDER BY id
            LIMIT $PAGE_SIZE
        ) sub;
    ")

    # No more rows to transfer
    if [ -z "$next_max_id" ]; then
        break
    fi

    echo "  Chunk $chunk: ids $((last_id + 1))..$next_max_id"

    psql "$LOCAL_DB" -c "
        COPY (
            SELECT * FROM geodata_line
            WHERE id > $last_id AND id <= $next_max_id
            ORDER BY id
        ) TO stdout
    " | psql "$PROD_DB" -c "COPY geodata_line FROM stdin;"

    last_id=$next_max_id
done

# ── Phase 3: Reset primary key sequences ────────────────────────────
#
# COPY inserts rows with explicit ids but does not advance the PostgreSQL
# auto-increment sequences. Without this step, the next Django-created Map
# or Line would collide with imported rows.

echo ">>> Phase 3: Resetting primary key sequences"

psql "$PROD_DB" -c "SELECT setval(pg_get_serial_sequence('geodata_map', 'id'), (SELECT MAX(id) FROM geodata_map));"
psql "$PROD_DB" -c "SELECT setval(pg_get_serial_sequence('geodata_line', 'id'), (SELECT MAX(id) FROM geodata_line));"

echo ">>> Done. Lines transferred up to id $last_id."
