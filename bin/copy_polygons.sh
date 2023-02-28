#!/bin/bash
# This script is called by the first_deploy hook

set -exv

echo ">>> Copying polygons from parent database"

# Scalingo requires you to run this script to update postgres' version
# Note: dbclient-fetcher installs binary in $HOME/bin
dbclient-fetcher psql 13

# Clear existing polygons in staging database
# Watch out! Don't empyt $PARENT_DATABASE_URL, it's the production database
$HOME/bin/psql -d $DATABASE_URL -c "DELETE FROM geodata_zone;"

nb_zones=$($HOME/bin/psql -d $PARENT_DATABASE_URL -t -c "SELECT COUNT(*) FROM geodata_zone;")
page_size=1000
nb_steps=$((nb_zones/page_size+1))

i=0
while [ $i -lt $nb_steps ]; do
    echo ">>> Copying polygons from parent database: step $i / $nb_steps"
    offset=$((i*page_size))
    query="COPY (SELECT * from geodata_zone ORDER BY id LIMIT $page_size OFFSET $offset) TO stdout"
    echo "$query"
    $HOME/bin/psql -d $PARENT_DATABASE_URL -c "$query" | $HOME/bin/psql -d $DATABASE_URL -c "COPY geodata_zone FROM stdin;"

    i=$((i+1))
done

echo ">>> Leaving the copy polygons script"
