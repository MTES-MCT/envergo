#!/bin/bash
# This script is ran by scalingo upon creating new review apps

echo ">>> Starting the first_deploy hook"

# Let's seed the database
PG_OPTIONS="--clean --if-exists --no-owner --no-privileges --no-comments"
PG_EXCLUDE="-N information_schema -N ^pg_* --exclude-table-data geodata_zone "
pg_dump $PG_OPTIONS $PG_EXCLUDE --dbname $PARENT_DATABASE_URL --format c --file /tmp/dump.pgsql
pg_restore $PG_OPTIONS --dbname $DATABASE_URL /tmp/dump.pgsql
psql -d $DATABASE_URL -c 'CREATE EXTENSION IF NOT EXISTS postgis;'
# psql -d $DATABASE_URL -c 'CREATE EXTENSION IF NOT EXISTS unaccent;'

# Clean dump file
rm /tmp/dump.pgsql

# Warning! This hook replaces the `post_deploy` hook that we still want to run
bash $HOME/bin/post_deploy.sh

echo ">>> Leaving the first_deploy hook"
