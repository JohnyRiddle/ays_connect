#!/bin/sh
set -eu
umask 077
# Fail before mkdir, pg_dump, tar or retention. No retention is implemented.
awk -v dev="$EXPECTED_BACKUP_DEVICE" '
 $5 == "/backups" && $3 == dev {
   for(i=6;i<=NF;i++) if($i=="-" && $(i+1)=="ext4" && $(i+2)=="/dev/mapper/objects-220ffac-recovery") good=1
 }
 END {exit !good}
' /proc/self/mountinfo || { echo 'STOP: encrypted backup mount not verified' >&2; exit 78; }
test -d /backups
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="/backups/${timestamp}"
mkdir "$destination"
pg_dump --format=custom --no-owner --no-acl --file="$destination/database.dump"
tar -C /source -czf "$destination/media.tar.gz" media
(cd "$destination"; sha256sum database.dump media.tar.gz > SHA256SUMS; sha256sum -c SHA256SUMS; pg_restore --list database.dump >/dev/null; tar -tzf media.tar.gz >/dev/null)
echo "backup_completed=$timestamp retention=disabled encrypted_mount=verified"
