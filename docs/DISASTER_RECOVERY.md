# Disaster recovery

## Recovery sequence

1. Declare incident and preserve failed host/storage; record last known healthy timestamp.
2. Provision a new Docker host, enable NTP/firewall and restore the approved untracked environment through the secret channel.
3. Verify `SHA256SUMS`; restore PostgreSQL custom dump into an isolated database first.
4. Restore media archive and verify representative attachment checksums. The archive contains a top-level `media/` directory; when the destination itself is the media volume root, extract with `tar --strip-components=1` to avoid a nested `media/media` path.
5. Deploy the matching application commit, migrate forward, start database/web/workers.
6. Validate login, Task, Request, SLA, Notification, Performance and protected attachment download.
7. Inspect queues/heartbeats, then reopen traffic and observe.

RPO equals actual backup cadence (currently daily). RTO is measured by each restore rehearsal and must be recorded in the release report; no unmeasured enterprise guarantee is claimed. A backup volume on the same host must be replicated off-host.

Never restore over the live database as a test. The provided `deployment/restore-smoke.sh` uses a disposable database and force-cleans it on exit.

The Phase 1.6A rehearsal restored a production-like Employee/Task/Request/SLA/Notification/Performance scenario into a separate PostgreSQL container and separate media volume. Database/media archive verification, canonical relationships, protected download and two independent attachment SHA-256 chains passed. Backup duration was 0.601 s; isolated DB/media restore was 10.578 s including the first helper-image pull.
