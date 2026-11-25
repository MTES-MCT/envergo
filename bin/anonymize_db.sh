#!/bin/bash
# Pseudonymize or anonymize personal data in the database at the given url.
#
# Modes:
# - pseudonymization: rewrites contact data (emails, names, phones,
#   companies) and removes secrets (passwords, sessions, OTP keys, tokens),
#   keeping business data so the copy still runs the application (review
#   apps, local dev).
# - anonymization: pseudonymization, plus the removal of every personal,
#   sensitive or geolocated datum that statistics do not need (stats copy).
#   The result is no longer meant to run the application.
#
# Personal columns are listed explicitly: a new model field holding personal
# data must be added here, or it reaches every copy untouched.
#
# IRREVERSIBLE. The target must always be a disposable copy, never
# production. The url is a mandatory explicit argument so that every caller
# names its target deliberately; automated callers must only ever hold
# credentials that cannot reach production (see README, section
# "Anonymisation d'une base de données").

set -euo pipefail

usage() {
    echo "Usage: $0 --mode=pseudonymization|anonymization <database-url>" >&2
    exit 1
}

if [ $# -ne 2 ]; then
    usage
fi
case "$1" in
    --mode=pseudonymization) MODE=pseudonymization ;;
    --mode=anonymization) MODE=anonymization ;;
    *) usage ;;
esac
DB_URL="$2"

# On Scalingo, dbclient-fetcher installs psql outside the PATH.
PSQL_BIN="${PSQL_BIN:-psql}"

# Identify the target by asking the server itself, not by parsing the url.
db_name=$("$PSQL_BIN" "$DB_URL" -tA -c 'SELECT current_database()')

# Interactive runs must confirm the target by name; automated callers have
# no tty and are covered by the credential rule in the header.
if [ -t 0 ]; then
    echo "About to IRREVERSIBLY process (mode: $MODE) this database:"
    "$PSQL_BIN" "$DB_URL" --quiet -c '\conninfo'
    read -r -p "Type the database name to confirm: " answer
    if [ "$answer" != "$db_name" ]; then
        echo "Confirmation failed, aborting." >&2
        exit 1
    fi
fi

# Rewritten values derive from primary keys: never NULL, and unique where
# the column requires it (users_user.email).
read -r -d '' PSEUDONYMIZATION_SQL <<'SQL' || true
UPDATE users_user
   SET email = 'user-' || id || '@example.org',
       name = 'Utilisateur ' || id
 WHERE NOT is_staff;

-- '!' is a hash no password matches: every account is locked.
UPDATE users_user SET password = '!';

TRUNCATE django_session, otp_totp_totpdevice, django_admin_log;

UPDATE petitions_invitationtoken SET token = gen_random_uuid()::text;

UPDATE evaluations_request SET obfuscation_key = gen_random_uuid();

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

-- The raw dossier holds the applicant's identity and contact data.
UPDATE petitions_petitionproject SET demarche_numerique_raw_dossier = '{}';

SQL

# Applied on top of PSEUDONYMIZATION_SQL in anonymization mode. Columns are
# emptied (NULL where allowed, else an empty value) rather than rewritten,
# except where a constraint or a statistic needs a value.
read -r -d '' ANONYMIZATION_SQL <<'SQL' || true
-- Removes the lat/lng query parameters of a moulinette url, keeping the
-- simulation inputs that statistics rely on.
CREATE FUNCTION pg_temp.strip_geo(url text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT regexp_replace(
        regexp_replace(url, '(?<=[?&])(lat|lng)=[^&#]*&?', '', 'g'),
        '[?&](?=#|$)', '')
$$;

-- Tables without statistical value. PostgreSQL only truncates a referenced
-- table together with the tables referencing it, even empty ones: hence
-- auth_permission, its join tables and django_admin_log next to
-- django_content_type.
TRUNCATE analytics_cspreport,
         confs_hostedfile,
         evaluations_regulatorynoticelog,
         evaluations_requestfile,
         django_migrations,
         django_content_type,
         auth_permission,
         auth_group_permissions,
         users_user_user_permissions,
         django_admin_log,
         geodata_catchmentareatile,
         geodata_line,
         geodata_zone;

UPDATE users_user
   SET email = 'user-' || id || '@example.org',
       name = 'Utilisateur ' || id;

-- References open the public notice pages.
UPDATE evaluations_evaluation
   SET reference = 'REF-' || uid,
       application_number = '',
       evaluation_file = NULL,
       project_description = '',
       address = '',
       details_md = '',
       details_html = '',
       rr_mention_md = '',
       rr_mention_html = '',
       moulinette_url = pg_temp.strip_geo(moulinette_url),
       moulinette_data = NULL,
       other_contacts = '';

UPDATE evaluations_evaluationversion SET content = '', message = '';

UPDATE evaluations_evaluationsnapshot
   SET payload = '{}',
       moulinette_url = pg_temp.strip_geo(moulinette_url);

UPDATE evaluations_request
   SET reference = 'REF-' || id,
       address = '',
       moulinette_url = pg_temp.strip_geo(moulinette_url),
       application_number = '',
       project_description = '',
       additional_data = NULL,
       other_contacts = '';

UPDATE petitions_petitionproject
   SET reference = 'REF-' || id,
       moulinette_url = pg_temp.strip_geo(moulinette_url),
       original_multi_category_moulinette_url =
           pg_temp.strip_geo(original_multi_category_moulinette_url),
       demarche_numerique_dossier_number = NULL,
       demarche_numerique_dossier_id = NULL,
       demarche_numerique_prefill_url = NULL,
       dn_archive = NULL,
       instructor_free_mention = '',
       instructor_private_mention = '';

UPDATE petitions_simulation
   SET moulinette_url = pg_temp.strip_geo(moulinette_url),
       comment = '';

UPDATE petitions_resultsnapshot
   SET payload = '{}',
       moulinette_url = pg_temp.strip_geo(moulinette_url);

UPDATE petitions_statuslog SET update_comment = '', applicant_message = '';

-- Hedge geometries; lengths stay in their own columns.
UPDATE hedges_hedgedata SET data = '[]';

-- PACAGE numbers identify farmers. Nothing references this primary key.
UPDATE hedges_pacage p
   SET pacage_num = 'PACAGE-' || n.rank
  FROM (SELECT pacage_num, row_number() OVER () AS rank FROM hedges_pacage) n
 WHERE p.pacage_num = n.pacage_num;

UPDATE urlmappings_urlmapping SET url = pg_temp.strip_geo(url);

UPDATE analytics_event
   SET metadata = CASE
           WHEN metadata ? 'url' THEN jsonb_set(
               metadata - 'lat' - 'lng' - 'address',
               '{url}',
               to_jsonb(pg_temp.strip_geo(metadata ->> 'url')))
           ELSE metadata - 'lat' - 'lng' - 'address'
       END
 WHERE jsonb_typeof(metadata) = 'object';

-- One salt per run: visitors stay countable within a copy, but no value
-- matches a real cookie or email hash.
UPDATE analytics_event e
   SET session_key = md5(e.session_key || s.salt),
       unique_id = md5(e.unique_id || s.salt)
  FROM (SELECT gen_random_uuid()::text AS salt) s;

-- Prefectural orders live in a public-read bucket: the path is the secret.
UPDATE petitions_statuslog SET prefectural_order = '';
SQL

echo "Processing database '$db_name' (mode: $MODE)..."

# Both modes run in a single transaction: a failure leaves the base untouched.
{
    printf '%s\n' "$PSEUDONYMIZATION_SQL"
    if [ "$MODE" = anonymization ]; then
        printf '%s\n' "$ANONYMIZATION_SQL"
    fi
} | "$PSQL_BIN" "$DB_URL" --quiet --single-transaction --set ON_ERROR_STOP=1 >/dev/null

echo "Processing complete (mode: $MODE)."
