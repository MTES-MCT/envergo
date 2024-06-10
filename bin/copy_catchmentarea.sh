#!/bin/bash
# This script is called by the first_deploy hook
# This script is used to copy catchment area tiles from the parent database to the staging database
# We need to do this using dummy sql queries — and not pg_dump/pg_restore — because
# not filtering the data we copy uses too much resources and makes the process crash

set -exv

echo ">>> Copying catchment area tiles from parent database"

# Clear existing catchment area tile in staging database
# Watch out! Don't empty $PARENT_DATABASE_URL, it's the production database
$HOME/bin/psql -d $DATABASE_URL -c "DELETE FROM geodata_catchmentareatile;"

nb_tiles=$($HOME/bin/psql -d $PARENT_DATABASE_URL -t -c "SELECT COUNT(*) FROM geodata_catchmentareatile c WHERE c.copy_to_staging IS true;")
page_size=1000
nb_steps=$((nb_tiles/page_size+1))

i=0
while [ $i -lt $nb_steps ]; do
    echo ">>> Copying catchment area tiles from parent database: step $i / $nb_steps"
    offset=$((i*page_size))
    query="COPY (SELECT c.* FROM geodata_catchmentareatile c WHERE c.copy_to_staging IS true ORDER BY c.id LIMIT $page_size OFFSET $offset) TO stdout"
    echo "$query"
    $HOME/bin/psql -d $PARENT_DATABASE_URL -c "$query" | $HOME/bin/psql -d $DATABASE_URL -c "COPY geodata_catchmentareatile FROM stdin;"

    i=$((i+1))
done

echo ">>> Leaving the copy catchment area tiles script"
