# Work Core v1.0 release checklist

Статусы: только `PASS`, `FAIL`, `PENDING`, `N/A` с обоснованием. Незапущенный пункт не считается PASS.

| Gate | Status | Evidence / blocker |
|---|---|---|
| Phase 1.5 checkpoint | PASS | `0068d12`, clean initial baseline |
| Functional scope freeze | PASS | Только security, correctness, recovery, deployment и UX hardening |
| Authentication / refresh / logout | PASS | Disabled User/Employee, immediate access denial, generic errors, throttle, rotation and blacklist regressions |
| RBAC / IDOR / nested visibility | PASS | PostgreSQL domain suites cover People, Tasks, Requests, SLA, notifications, performance and operations negative access |
| Attachment security / protected download | PASS | Size, MIME, basename, signatures, executable suffix positions and protected endpoint tests |
| Secrets / demo credential audit | PASS | Local secrets ignored; safe examples; built assets contain no demo credential values |
| Django deploy check | PASS | No runtime errors; W005/W021 accepted pending real hostname/subdomain preload policy; schema-only W001/W002 documented debt |
| Clean PostgreSQL migrations | PASS | PostgreSQL 17, clean migrations/bootstrap and `makemigrations --check` |
| Upgrade rehearsal twice | PASS | Two isolated copies `ays_upgrade_rc_a` and `ays_upgrade_rc_b`; migrations/check/data counts preserved |
| Backend PostgreSQL suite | PASS | 254/254 including canonical production Outbox entity-type regression |
| Concurrency / locking | PASS | 20 Task + 20 Request numbering; optimistic locking, watcher, queue and SKIP LOCKED regressions |
| Worker heartbeat/recovery | PASS | Six deployed worker categories, OK/STALE/UNKNOWN, latest-instance selection, run IDs and restart recovery |
| Outbox / notification / performance recovery | PASS | Bounded retries, poison terminal state, explicit retry command, UNKNOWN no-resend and stale claim recovery |
| Correlation and safe logging | PASS | Validated/generate UUID, response header and structured request context without bodies/tokens |
| Production-like compose security | PASS | No demo seed; internal DB/Redis/Gunicorn; full workers; Caddy-only 80/443; production Caddy config validates |
| Container/PostgreSQL/Redis restart | PASS | Full stop/start recovered healthy; user/employee/migration counts identical |
| Backup / isolated restore | PASS | DB/media checksums and isolated restore; 3.88 s; existing Employee and PerformanceAggregate verified |
| Full restore sample domains | PASS | Marked Employee/Task/Request/execution Task/SLA/IN_APP Notification/Performance scenario restored with relationships and both attachment hashes MATCH |
| Frontend production build / dependency audit | PASS | Vite production build; `npm audit` 0 vulnerabilities |
| SPA fallback / cache / headers | PASS | Direct Tasks/Requests/Notifications/Performance/Settings routes return 200; index no-cache; immutable assets |
| Production Work Core frontend UX | PASS | Production Tasks/Requests lists, create/detail/actions, dynamic forms, collaboration, SLA and execution Tasks use internal API; legacy Tasks runtime usage is zero |
| Backend local E2E | PASS | Full PostgreSQL suite covers Task, Request, Request→Task, SLA/escalation/notification and performance event chains |
| Browser responsive/auth UX | PASS | Playwright local pilot smoke 7/7 covers SPA fallback and authenticated production Task/Request lists; trusted public CA remains a server gate |
| Synthetic performance | PASS | 100 employees, 10k Tasks, 10k Requests, 130k facts; 56.715 s; indexed query 0.164 ms |
| Backend dependency audit | PASS | Django 5.1.5→5.2.17 and SimpleJWT 5.4.0→5.5.1; `pip-audit`: no known vulnerabilities |
| Release documentation | PASS | Required Phase 1.6, deployment, recovery, operations and quickstart documents exist |
| Trusted HTTPS / hostname / DNS | PENDING | Requires production server and public hostname |
| Firewall / NTP / host reboot | PENDING | Requires production server access |
| Real Telegram smoke | PENDING | Requires trusted public webhook and real bot binding |
| Email smoke | N/A | Email disabled; reclassify to PENDING if production SMTP is enabled |
| Real employees / RBAC / UAT | PENDING | Requires production organization bootstrap and users |

Current status:

```text
PHASE 1.6 — LOCAL GATES PASS
PRODUCTION GATES — PENDING
WORK CORE v1.0 — NOT YET
```

Local gates are complete. Do not label Work Core v1.0 production-ready until the remaining server-dependent trusted HTTPS, reboot, Telegram, real RBAC/user UAT and observation rows pass.
