#!/bin/sh
set -eu

ensure_database() {
  psql -v ON_ERROR_STOP=1 -d postgres \
    -v db_user="$1" -v db_password="$2" -v db_name="$3" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user') \gexec
ALTER ROLE :"db_user" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'db_password';
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec
ALTER DATABASE :"db_name" OWNER TO :"db_user";
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"db_name" TO :"db_user";
SQL
}

ensure_database "$MESSENGER_DB_USER" "$MESSENGER_DB_PASSWORD" "$MESSENGER_DB_NAME"
ensure_database "$FILE_SERVICE_DB_USER" "$FILE_SERVICE_DB_PASSWORD" "$FILE_SERVICE_DB_NAME"
psql -v ON_ERROR_STOP=1 -d postgres -c 'REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;'
echo "databases ready: $MESSENGER_DB_NAME, $FILE_SERVICE_DB_NAME"
