#!/bin/sh
set -eu

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="/backups/${timestamp}"
mkdir -p "${destination}"
pg_dump --format=custom --file="${destination}/database.dump"
tar -C /source -czf "${destination}/media.tar.gz" media
sha256sum "${destination}/database.dump" "${destination}/media.tar.gz" > "${destination}/SHA256SUMS"
find /backups -mindepth 1 -maxdepth 1 -type d -mtime "+${BACKUP_RETENTION_DAYS}" -exec rm -rf -- {} +
echo "backup_completed=${timestamp}"
