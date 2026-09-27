# Production deployment

> Для интегрированного релиза People + Projects + iiko + Cards от 27.09.2026
> обязательны inventory, migration delta, off-host restore gate и порядок переключения
> компонентов из
> [INTEGRATED_RELEASE_2026_09_27.md](INTEGRATED_RELEASE_2026_09_27.md). Этот runbook не
> разрешает deployment без immutable checkpoint и проверенного off-host restore point.

## Prerequisites

Linux host with current Docker Engine/Compose, persistent disk, NTP enabled, DNS A/AAAA record and inbound 80/443 only. PostgreSQL, Redis and backend ports stay on the internal Compose network.

1. Checkout an approved RC commit; never edit a running container.
2. Copy `.env.prod.example` to an untracked server env file and replace every `CHANGE_ME` out of band.
3. Set canonical hostname consistently in allowed hosts, trusted origins, public URL and Telegram webhook URL.
4. Take/verify backup before upgrade.
5. Run `docker compose --env-file <server-env> -f docker-compose.prod.yml config --quiet`, then `up -d --build`. The one-shot init service applies migrations, permissions and static collection.
6. Start services and verify live, ready, protected system status and every worker heartbeat.
7. Verify HTTP→HTTPS, trusted certificate/renewal and SPA fallback.
8. Run acceptance personas and external-channel smoke.

Database migrations are forward-only. Application rollback is permitted only inside a documented schema compatibility window; never promise automatic schema reversal. Do not run `seed_demo`, synthetic benchmarks or fixtures in production.

Runtime backend uses an unprivileged user. Bootstrap init may use elevated filesystem rights only for static/media ownership. Canonical data is PostgreSQL; Redis loss must not destroy business state.

`deployment/Caddyfile.production` intentionally has no `tls internal`: Caddy must obtain a publicly trusted certificate for `PRODUCTION_HOST`. Only ports 80/443 are published; PostgreSQL, Redis and Gunicorn stay internal. Do not deploy while the Work Core frontend row in the release checklist is `FAIL`.

## Maintenance backup and ordinary resume

Define the production Compose command without printing the env file:

```bash
dc='docker compose --env-file .env.production -p ays-connect-production -f docker-compose.prod.yml -f docker-compose.iiko.yml'
writers='proxy backend recurrence_worker schedule_worker sla_worker escalation_worker notification_worker performance_worker'
```

Record `ps`, image digests, release markers and the applied migration plan. Stop all
public and background writers, leaving `db`, `redis` and `backup` running:

```bash
$dc stop -t 30 $writers
$dc ps
```

Create a fresh PostgreSQL custom dump and media archive without running the retention
step. Verify server-side SHA-256, copy the files to the approved off-host target, verify
SHA-256 there, and complete an isolated restore before any migration. Preserve existing
backups.

For an ordinary resume after a backup-only window, start the existing containers
directly. **Do not use `docker compose start backend ...`**: Compose follows
`depends_on` and can automatically run `init` and `frontend_assets`.

```bash
docker start \
  "$($dc ps -aq backend)" \
  "$($dc ps -aq recurrence_worker)" \
  "$($dc ps -aq schedule_worker)" \
  "$($dc ps -aq sla_worker)" \
  "$($dc ps -aq escalation_worker)" \
  "$($dc ps -aq notification_worker)" \
  "$($dc ps -aq performance_worker)"

# Wait until backend is healthy, then expose traffic.
docker start "$($dc ps -aq proxy)"
```

Confirm the same release marker, migration-plan hash, RBAC fingerprints, eleven expected
running services, backend readiness and external HTTPS. If any check differs, keep
maintenance active and investigate.

## Controlled release sequence

An old backup is evidence for its capture time only. Immediately before migrations,
repeat the maintenance backup procedure and require all of the following: server-side
checksums, completed off-host copy, matching off-host checksums, isolated database/media
restore, validated constraints and an internal-only restore network with no application,
workers, schedules or real integration credentials.

Build and inspect the immutable release images **before maintenance**, while the old
version is still serving. Record both old and new image digests and confirm that the
`init` service resolves to the newly built, verified release image. After maintenance
begins and writers are stopped, keep the database and Redis running. Run the release
init exactly once and without dependency traversal:

```bash
$dc build init backend frontend_assets \
  recurrence_worker schedule_worker sla_worker escalation_worker \
  notification_worker performance_worker

$dc run --rm --no-deps init
```

The controlled `init` invocation is the only permitted migration step. Review its full
output and stop if the applied plan differs from the approved plan. It may run
`seed_permissions`, which adds the release permission codes to the catalog and updates
their labels. It must not create or widen role/user grants. Compare RolePermission and
EmployeeRole fingerprints before and after and reject any grant change.

Publish frontend assets once, then recreate backend and workers from the same release
without starting `init` again:

```bash
$dc run --rm --no-deps frontend_assets
$dc up -d --no-deps --force-recreate \
  backend recurrence_worker schedule_worker sla_worker escalation_worker \
  notification_worker performance_worker
```

Wait for backend and every worker health check. Run migration status, logs, Outbox and
read-only People/JWT/Projects/Work/iiko/Cards/file-access smoke tests. Only after the
mandatory gate succeeds, recreate the proxy without dependencies:

```bash
$dc up -d --no-deps --force-recreate proxy
```

After proxy startup, external HTTPS smoke tests against the canonical production host
are mandatory: certificate validation, `/api/v1/health/live/`,
`/api/v1/health/ready/`, SPA load and authenticated read-only application routes. Keep
user writes closed until these checks pass, then explicitly record the time writes are
enabled again.

Keep previous images and the fresh pre-migration backup. If migrations changed data or
constraints, code rollback alone is insufficient. Database/media restore is permitted
only while writes remain closed and no new real data exists; after writes resume, require
a separate data-preservation decision.
