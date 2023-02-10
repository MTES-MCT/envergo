#!/bin/bash
# This script is called by the first_deploy hook

set -exv

echo ">>> Copying polygons from parent database"

# Scalingo requires you to run this script to update postgres' version
dbclient-fetcher psql 13

# Let's seed the database
PG_OPTIONS="--data-only --format=c --compress=9 --no-owner --no-privileges --no-comments"
PG_TABLE="--table=geodata_zone"

# Note: dbclient-fetcher installs binary in $HOME/bin
$HOME/bin/pg_dump $PG_OPTIONS $PG_TABLE --dbname $PARENT_DATABASE_URL --format c --file /tmp/polygons.pgsql
$HOME/bin/pg_restore $PG_OPTIONS --dbname $DATABASE_URL /tmp/polygons.pgsql

# Clean dump file
rm /tmp/polygons.pgsql

echo ">>> Leaving the copy polygons script"
