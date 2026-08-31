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
