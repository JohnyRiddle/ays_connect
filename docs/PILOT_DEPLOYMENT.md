# AYS Connect Work — Pilot Deployment

## Status

The repository contains a production-like Docker Compose topology for an internal
pilot. It does not declare Work Core v1.0. Local infrastructure was validated on
31 August 2026; trusted public HTTPS and real Telegram delivery are completed when
the server hostname and credentials are supplied.

## Architecture

```text
HTTP :80 -> HTTPS redirect
HTTPS :443 -> Caddy
                 |-> Vite production assets (SPA fallback)
                 |-> Django/Gunicorn API and Admin
                         |-> PostgreSQL 17
                         |-> Redis

Workers: recurrence, schedules, SLA, escalation, notifications
Storage: PostgreSQL, Redis, media, static, frontend, Caddy and backup volumes
```

PostgreSQL and backend ports are not published. Only Caddy exposes ports 80/443.
The frontend build is copied to a persistent asset volume by a one-shot container;
Caddy serves it directly and falls back to `index.html` for frontend routes.

## Host requirements

- Docker Engine with Compose v2;
- ports 80 and 443 available;
- sufficient disk space for PostgreSQL, media, images, logs and backups;
- for the server: DNS record pointing at the host and inbound TCP 80/443.

## Configuration and secrets

Generate the ignored local environment file once:

```powershell
.\deployment\New-PilotEnvironment.ps1
```

For a server, copy `.env.pilot.example` to an ignored environment file and provide
unique secrets through the host secret store. Required values include Django and
PostgreSQL secrets, actual hosts/origins, the public HTTPS URL, and—when enabled—new
Telegram and SMTP credentials. Never put the resulting file in Git or logs.

Local Caddy uses its internal CA. Import its root certificate into the local trust
store only on pilot workstations. A public hostname uses normal ACME certificates;
replace `tls internal` in the server-specific Caddy configuration at that point.

## Repeatable deployment

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml config --quiet
docker compose --env-file .env.pilot -f docker-compose.pilot.yml build
docker compose --env-file .env.pilot -f docker-compose.pilot.yml up -d
curl.exe -k https://localhost/api/v1/health/ready/
```

The one-shot `init` service applies existing migrations, seeds permissions and
collects static files. It never runs demo fixtures or destructive resets.

## Bootstrap and first users

Create the first administrator without placing the password on a command line:

```powershell
$env:PILOT_ADMIN_EMAIL = "admin@example.com"
$env:PILOT_ADMIN_USERNAME = "pilot-admin"
$credential = Get-Credential -UserName $env:PILOT_ADMIN_EMAIL
$env:PILOT_ADMIN_PASSWORD = $credential.GetNetworkCredential().Password
docker compose --env-file .env.pilot -f docker-compose.pilot.yml run --rm -e PILOT_ADMIN_EMAIL -e PILOT_ADMIN_USERNAME -e PILOT_ADMIN_PASSWORD backend python manage.py bootstrap_pilot_admin
Remove-Item Env:PILOT_ADMIN_PASSWORD
```

The idempotent command creates both the superuser and its Employee link and never
prints the password. Add only the real pilot subset:
LegalEntity, OrgUnit, Location, Position and 5–15 Employees. Use scoped RBAC roles;
do not grant GLOBAL scope merely for convenience.

## Telegram and Email

Email remains globally disabled until real SMTP is supplied. IN_APP continues to
work. Telegram remains disabled until a new bot token, username, webhook secret and
public HTTPS URL are configured. Then run:

```powershell
docker compose --env-file .env.pilot -f docker-compose.pilot.yml exec backend python manage.py configure_telegram_webhook
```

Complete real `/start <token>` linking and delivery before admitting pilot users.

## Pilot data

All data in this deployment is production data despite pilot status. Never use
`down -v`, reset the database, reload demo fixtures, fake migrations or delete media
without an explicit backup and approved procedure. Start with 5–10 real Request
Types, a small Task Template set and 2–3 understandable SLA levels.

## Rollback

Application rollback means rebuilding a previously recorded commit/image and
restarting services. Database migrations are forward-only; restore from a verified
backup when a database recovery is genuinely required. Do not automatically reverse
production migrations.

## Pilot restrictions

- limited internal user group;
- real operational data and planned maintenance windows;
- schema changes can continue during the pilot;
- Performance/Phase 1.5 may still add analytics;
- Phase 1.6 is required before a formal Work Core v1.0 release.

## Known local limitations

- `https://localhost` uses a Caddy internal CA until a real server hostname exists;
- Email and Telegram are disabled until real credentials are supplied;
- logout token revocation is not implemented by the current JWT API;
- OpenAPI generation still reports non-blocking annotation/name warnings;
- real-user Task, Request, SLA, escalation and Telegram acceptance remains a server gate.
