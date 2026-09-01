#!/bin/sh
set -eu

restore_database="${RESTORE_DATABASE:?RESTORE_DATABASE is required}"
latest="$(find /backups -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
test -n "${latest}"
sha256sum -c "${latest}/SHA256SUMS"
psql -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${restore_database} WITH (FORCE)" >/dev/null
psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${restore_database}" >/dev/null
pg_restore --exit-on-error --no-owner --dbname="${restore_database}" "${latest}/database.dump"
echo "upgrade_copy_ready=${restore_database}"
