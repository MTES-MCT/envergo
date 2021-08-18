#!/bin/bash
# This script is ran by scalingo upon creating new review apps

echo ">>> Starting the first_deploy hook"

# Let's seed the database
PG_OPTIONS="--clean --if-exists --no-owner --no-privileges --no-comments"
PG_EXCLUDE_SCHEMA="-N 'information_schema' -N '^pg_*'"
pg_dump $PG_OPTIONS $PG_EXCLUDE_SCHEMA --dbname $PARENT_DATABASE_URL --format c --file /tmp/dump.pgsql
pg_restore $PG_OPTIONS --dbname $DATABASE_URL /tmp/dump.pgsql
# psql -d $DATABASE_URL -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm;'
# psql -d $DATABASE_URL -c 'CREATE EXTENSION IF NOT EXISTS unaccent;'

# Warning! This hook replaces the `post_deploy` hook that we still want to run
bash $HOME/bin/post_deploy.sh

echo ">>> Leaving the first_deploy hook"
