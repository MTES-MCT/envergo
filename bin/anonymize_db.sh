#!/bin/bash
# Anonymize personal data in the database at the given url.
#
# IRREVERSIBLE. The target must always be a disposable copy, never
# production. The url is a mandatory explicit argument so that every caller
# names its target deliberately; automated callers must only ever hold
# credentials that cannot reach production (see README, section
# "Anonymisation d'une base de données").

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <database-url>" >&2
    exit 1
fi
DB_URL="$1"

# On Scalingo, dbclient-fetcher installs psql outside the PATH.
PSQL_BIN="${PSQL_BIN:-psql}"

# Identify the target by asking the server itself, not by parsing the url.
db_name=$("$PSQL_BIN" "$DB_URL" -tA -c 'SELECT current_database()')

# Interactive runs must confirm the target by name; automated callers have
# no tty and are covered by the credential rule in the header.
if [ -t 0 ]; then
    echo "About to IRREVERSIBLY anonymize this database:"
    "$PSQL_BIN" "$DB_URL" --quiet -c '\conninfo'
    read -r -p "Type the database name to confirm: " answer
    if [ "$answer" != "$db_name" ]; then
        echo "Confirmation failed, aborting." >&2
        exit 1
    fi
fi

echo "Anonymizing database '$db_name'..."

# Anonymized values derive from primary keys: never NULL, and unique where
# the column requires it (users_user.email).
"$PSQL_BIN" "$DB_URL" --quiet --single-transaction --set ON_ERROR_STOP=1 <<'SQL'
UPDATE users_user
   SET email = 'user-' || id || '@example.org',
       name = 'Utilisateur ' || id
 WHERE NOT is_staff;

UPDATE evaluations_evaluation
   SET urbanism_department_phone = '+33100000000',
       urbanism_department_emails = ARRAY['urbanisme-' || uid || '@example.org'],
       project_owner_emails = ARRAY['porteur-' || uid || '@example.org'],
       project_owner_phone = '+33100000000',
       project_owner_company = 'Entreprise ' || uid;

UPDATE evaluations_request
   SET urbanism_department_phone = '+33100000000',
       urbanism_department_emails = ARRAY['urbanisme-' || id || '@example.org'],
       project_owner_emails = ARRAY['porteur-' || id || '@example.org'],
       project_owner_phone = '+33100000000';

UPDATE evaluations_regulatorynoticelog
   SET frm = 'expediteur-' || id || '@example.org',
       "to" = ARRAY['destinataire-' || id || '@example.org'],
       cc = ARRAY['copie-' || id || '@example.org'],
       bcc = ARRAY['copie-cachee-' || id || '@example.org'];
SQL

echo "Anonymization complete."
