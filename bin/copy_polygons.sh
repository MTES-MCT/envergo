#!/bin/bash
# This script is called by the first_deploy hook

set -exv

echo ">>> Copying polygons from parent database"

# Scalingo requires you to run this script to update postgres' version

dbclient-fetcher psql 13

# Let's seed the database
PG_OPTIONS="--data-only --format=c --no-owner --no-privileges --no-comments"
PG_TABLE="--table=geodata_zone"

# Note: dbclient-fetcher installs binary in $HOME/bin
# $HOME/bin/pg_dump $PG_OPTIONS --compress=9 $PG_TABLE --dbname $PARENT_DATABASE_URL --format c --file /tmp/polygons.pgsql
# $HOME/bin/pg_restore $PG_OPTIONS --dbname $DATABASE_URL /tmp/polygons.pgsql

# Clean dump file
# rm /tmp/polygons.pgsql

# export PARENT_DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"

count=$($HOME/bin/psql -d $PARENT_DATABASE_URL -t -c "SELECT COUNT(*) FROM geodata_zone;")
$HOME/bin/psql -d $PARENT_DATABASE_URL -c "COPY (SELECT * from geodata_zone ORDER BY id limit 100) TO stdout" | $HOME/bin/psql -d $DATABASE_URL -c "COPY geodata_zone FROM stdin;"





echo ">>> Leaving the copy polygons script"
