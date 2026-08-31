#!/bin/sh
set -eu

restore_database="ays_restore_smoke"
latest="$(find /backups -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
test -n "${latest}"
sha256sum -c "${latest}/SHA256SUMS"

cleanup() {
  psql -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${restore_database} WITH (FORCE)" >/dev/null
}
trap cleanup EXIT
cleanup
psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${restore_database}" >/dev/null
pg_restore --exit-on-error --no-owner --dbname="${restore_database}" "${latest}/database.dump"
migrations="$(psql -d "${restore_database}" -tAc "SELECT count(*) FROM django_migrations WHERE app = 'performance'")"
aggregates="$(psql -d "${restore_database}" -tAc "SELECT count(*) FROM performance_performanceaggregate")"
test "${migrations}" -ge 2
echo "restore_smoke=PASS performance_migrations=${migrations} performance_aggregates=${aggregates}"
