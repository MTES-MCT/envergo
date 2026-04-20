#!/bin/bash
# This script is called by the first_deploy hook
# This script is used to copy Maps from the parent database to the staging database
# We need to do this using dummy sql queries — and not pg_dump/pg_restore — because
# not filtering the data we copy uses too much resources and makes the process crash

set -exv

echo ">>> Copying maps from parent database"

# Scalingo requires you to run this script to update postgres' version
# Note: dbclient-fetcher installs binary in $HOME/bin
dbclient-fetcher psql 13

# Clear existing maps in staging database
# Watch out! Don't empty $PARENT_DATABASE_URL, it's the production database
$HOME/bin/psql -d $DATABASE_URL -c "DELETE FROM geodata_map;"

nb_maps=$($HOME/bin/psql -d $PARENT_DATABASE_URL -t -c "SELECT COUNT(*) FROM geodata_map  WHERE copy_to_staging IS true;")
page_size=1000
nb_steps=$((nb_maps/page_size+1))

i=0
while [ $i -lt $nb_steps ]; do
    echo ">>> Copying maps from parent database: step $i / $nb_steps"
    offset=$((i*page_size))
    query="COPY (SELECT * from geodata_map m WHERE copy_to_staging IS true ORDER BY id LIMIT $page_size OFFSET $offset) TO stdout"
    echo "$query"
    $HOME/bin/psql -d $PARENT_DATABASE_URL -c "$query" | $HOME/bin/psql -d $DATABASE_URL -c "COPY geodata_map FROM stdin;"

    i=$((i+1))
done

echo ">>> Leaving the copy maps script"
