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
#        scalingo --app envergo-haie db-tunnel SCALINGO_POSTGRESQL_URL
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
# To resume after a failure, set START_CHUNK to skip already-transferred
# chunks:
#
#    LOCAL_DB="..." PROD_DB="..." START_CHUNK=1500 bash bin/copy_lines_to_prod.sh
#
# Tuning: PAGE_SIZE defaults to 5000. Increase for speed, decrease if the
# production DB struggles:
#
#    LOCAL_DB="..." PROD_DB="..." PAGE_SIZE=10000 bash bin/copy_lines_to_prod.sh
#
# Cleanup after failure
# =====================
#
# If the script fails mid-run, some Lines will already be in production.
# Since local PKs are newer than any existing production PK, you can delete
# them with:
#
#    psql "$PROD_DB" -c "DELETE FROM geodata_line WHERE created_at >= '<import_start_time>';"
#
# Then re-run the script (optionally with START_CHUNK to skip Maps).

set -euo pipefail

PAGE_SIZE=${PAGE_SIZE:-5000}
START_CHUNK=${START_CHUNK:-0}

if [ -z "${LOCAL_DB:-}" ] || [ -z "${PROD_DB:-}" ]; then
    echo "Error: LOCAL_DB and PROD_DB environment variables are required."
    echo "See the header of this script for usage instructions."
    exit 1
fi

# ── Phase 1: Transfer Maps ──────────────────────────────────────────

if [ "$START_CHUNK" -eq 0 ]; then
    echo ">>> Phase 1: Transferring Maps referenced by Lines"

    nb_maps=$(psql "$LOCAL_DB" -t -A -c "
        SELECT COUNT(DISTINCT map_id) FROM geodata_line;
    ")
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
else
    echo ">>> Phase 1: Skipped (START_CHUNK=$START_CHUNK)"
fi

# ── Phase 2: Transfer Lines (paginated) ─────────────────────────────

echo ">>> Phase 2: Transferring Lines"

nb_lines=$(psql "$LOCAL_DB" -t -A -c "SELECT COUNT(*) FROM geodata_line;")
nb_steps=$(( (nb_lines + PAGE_SIZE - 1) / PAGE_SIZE ))

echo "  $nb_lines lines to transfer in $nb_steps chunks of $PAGE_SIZE"

i=$START_CHUNK
while [ "$i" -lt "$nb_steps" ]; do
    offset=$((i * PAGE_SIZE))
    echo "  Chunk $((i + 1)) / $nb_steps (offset $offset)"

    psql "$LOCAL_DB" -c "
        COPY (
            SELECT * FROM geodata_line
            ORDER BY id
            LIMIT $PAGE_SIZE OFFSET $offset
        ) TO stdout
    " | psql "$PROD_DB" -c "COPY geodata_line FROM stdin;"

    i=$((i + 1))
done

echo ">>> Done. $nb_lines lines transferred."
