# Production deployment

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
