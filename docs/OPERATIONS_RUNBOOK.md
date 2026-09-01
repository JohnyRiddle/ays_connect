# AYS Connect Work — Operations Runbook

Commands below assume the repository root and the local ignored `.env.pilot` file.
Define `$pilot = @('--env-file','.env.pilot','-f','docker-compose.pilot.yml')` if desired.

## Status and health

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml ps -a
curl.exe -k https://localhost/api/v1/health/live/
curl.exe -k https://localhost/api/v1/health/ready/
docker system df
Get-PSDrive -PSProvider FileSystem
```

Readiness checks PostgreSQL without exposing its address or credentials. Liveness
returns only service and safe build version information.

Administrators use `GET /api/internal/v1/system/status/` for safe version, worker heartbeat and queue counts. `live` never depends on DB/providers; `ready` checks DB. Worker status is deliberately separate to avoid restart storms.

## Logs

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml logs --tail 200 backend
docker compose --env-file .env.pilot -f docker-compose.pilot.yml logs --tail 200 sla_worker escalation_worker notification_worker
docker compose --env-file .env.pilot -f docker-compose.pilot.yml logs -f proxy
```

Docker JSON logs rotate at 10 MB with five files per service. Do not paste secrets or
full sensitive payloads into operational tickets.

## Restart and update

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml restart backend
docker compose --env-file .env.pilot -f docker-compose.pilot.yml restart sla_worker escalation_worker notification_worker
docker compose --env-file .env.pilot -f docker-compose.pilot.yml build
docker compose --env-file .env.pilot -f docker-compose.pilot.yml up -d
```

Services use `restart: unless-stopped` and resume after Docker/host restart.
After restart, confirm that `last_seen_at` advances in system status. Polling cadence is 5–60 seconds; the default stale threshold is 180 seconds (`WORKER_STALE_SECONDS`).

## Migrations and permissions

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml run --rm init
docker compose --env-file .env.pilot -f docker-compose.pilot.yml run --rm backend python manage.py check
docker compose --env-file .env.pilot -f docker-compose.pilot.yml run --rm backend python manage.py makemigrations --check --dry-run
```

Never generate, fake or reverse migrations during deployment.

## Outbox and notifications

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py shell -c "from django.db.models import Count; from events.models import OutboxEvent; print(list(OutboxEvent.objects.values('status').annotate(total=Count('id'))))"
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py shell -c "from django.db.models import Count; from notifications.models import NotificationDelivery; print(list(NotificationDelivery.objects.values('status','channel').annotate(total=Count('id'))))"
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py process_notifications --batch-size 100 --reconcile
```

The notification worker consumes `notification.requested` Outbox events; other domain events remain an
auditable integration stream until a registered consumer exists.

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py reconcile_outbox --dry-run
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py reconcile_outbox
```

Outbox uses at most five automatic attempts with bounded backoff. Terminal poison events remain stored and require diagnosis plus explicit operator action. Notification `UNKNOWN/DELIVERY_OUTCOME_UNKNOWN` is never automatically resent.

After repairing the idempotent consumer, requeue exactly one terminal event explicitly:

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py retry_outbox_event <UUID> --confirm
```

The command fails closed without `--confirm`, for a non-terminal event, or for an unknown UUID.

Heartbeat rows are instance history. The status API reports the most recently seen instance per worker and emits `WORKER_UNKNOWN` when an expected worker has never reported. Runtime categories are recurrence, schedule (including learning deadlines), SLA, escalations, notifications and performance. Outbox is transactional infrastructure; it has no standalone production worker in the current architecture.

Login throttling uses Django's bounded process-local cache and does not depend on Redis. Redis loss therefore cannot take login down. A process/container restart clears counters (documented fail-open restart behavior); the mechanism does not create a permanent account lock.

## SLA and escalations

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py process_sla --batch-size 100
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py process_escalations --batch-size 100
```

Normal cadences are 30 seconds for SLA/escalation and 5 seconds for notifications.

## Backups

The backup service creates a PostgreSQL custom dump, media archive and SHA-256 file
daily, retaining seven daily directories by default. Run an immediate backup:

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml run --rm backup sh -ec '/opt/ays/backup.sh'
docker compose --env-file .env.pilot -f docker-compose.pilot.yml logs --tail 20 backup
```

Backup data lives in the `ays-connect-pilot_backup_data` volume. Copy it to separate
storage regularly; a volume on the same disk is not protection from host loss.

## Restore test

Restore only into an isolated database first. Verify SHA-256, restore the custom dump,
verify expected rows and inspect the media archive. Never overwrite the live pilot DB
as a smoke test. The local validation restored 57 migration records and verified the
media archive on 31 August 2026.

## Telegram webhook

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py configure_telegram_webhook
```

Run only after the real HTTPS URL and new credentials are present. The command must
not be run merely to test configuration against a fake/local callback URL.

## Incident quick check

1. Check disk space and `docker compose ps -a`.
2. Check readiness and DB health.
3. Inspect backend and relevant worker logs.
4. Inspect Outbox/notification backlogs without dumping payloads.
5. Take an immediate backup before invasive recovery.
6. Restart only the affected service; do not delete volumes.

## Incident procedures

- Backend unavailable: check proxy/backend health and DB readiness, then restart only backend.
- PostgreSQL unavailable: stop writes, inspect disk/container logs, restore only through the DR procedure.
- Worker stale: inspect last error/backlog, restart that worker and verify heartbeat recovery.
- Notifications stuck: reconcile stale deliveries; never automatically resend `UNKNOWN`.
- SLA backlog: run one bounded `process_sla` cycle and inspect errors before restarting the loop.
- Disk low: prune only documented build cache/expired backups; never delete runtime volumes.
- Backup failed: record RPO risk, correct capacity/permissions, then run and verify an immediate backup.
