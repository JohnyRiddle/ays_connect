# Phase 1.6A — Production Work Frontend

Дата gate: 01.09.2026.

## Результат

Production Tasks и Service Requests доступны в SPA через `/tasks/...` и `/requests/...`. Runtime использует `/api/internal/v1/tasks/` и `/api/internal/v1/requests/`; legacy Tasks API оставлен только как недостижимый совместимый код и отсутствует в production bundle.

Реализованы list/create/detail, фильтры и пагинация, lifecycle actions с optimistic locking, dynamic request form, PUBLIC/INTERNAL comments и attachments, watchers, checklists, activity/history/SLA, а также атомарное создание execution Task из заявки через существующий backend service.

Минимальные backend contract additions: read-only AssignmentTarget lookup и display-поля сотрудников/назначений. Доменная архитектура, lifecycle services и транзакционные границы не менялись.

## Проверки

- PostgreSQL backend suite: `254/254 PASS`;
- AssignmentTarget API regression: `2/2 PASS`;
- `manage.py check`: PASS;
- `makemigrations --check --dry-run`: PASS, no changes;
- production frontend Docker build: PASS;
- Playwright local pilot smoke: `7/7 PASS`;
- authenticated API smoke: profile, tasks, requests, catalog, assignment targets — HTTP 200;
- direct route/refresh: `/tasks`, `/tasks/new`, `/tasks/:id`, `/requests`, `/requests/new`, `/requests/:id`, `/notifications/settings` — HTTP 200;
- `git diff --check`: PASS.

## Business Restore Gate

Controlled scenario `RELEASE-GATE-1.6A` was created through production admin/config APIs, Work APIs, domain services and workers on top of the preserved pilot state. It contains an Employee, active Task, Task comment/attachment, active Request with immutable dynamic schema values, public comment/attachment, execution Task relation, SLA instance with achieved response and breached resolution metric, IN_APP escalation notification, six Performance facts and 300 employee aggregates.

- production DB/media backup: PASS, `0.601 s`;
- backup archive checksums and expected media entries: PASS;
- isolated PostgreSQL/media restore: PASS, `10.578 s` including first-time helper image pull;
- restored `migrate --check` and Django check: PASS;
- Employee/Task/Request/SLA/Notification/Performance: PASS;
- Task and Request collaboration: PASS;
- Request → execution Task relationship: PASS;
- Task attachment source DB/physical/restored DB/restored physical SHA-256: MATCH;
- Request attachment source DB/physical/restored DB/restored physical SHA-256: MATCH;
- protected downloads after restore: unauthenticated 401, authenticated 200;
- restored worker replay: no duplicate Task, Request, Notification, SLA instance or resolution cycle.

Gate found and fixed one real defect: `enqueue_performance` filtered lowercase entity types while production Outbox publishes `Task`, `ServiceRequest` and `SLAInstance`. The command now accepts canonical values and legacy lowercase values; a regression test raises the backend baseline to `254/254`.

The restore rehearsal also confirmed that `media.tar.gz` contains a top-level `media/` directory. When restoring directly into a media volume it must be extracted with `--strip-components=1`.

## Gate status

`PHASE 1.6A — COMPLETE`

`PRODUCTION WORK FRONTEND — COMPLETE`

`BUSINESS-OBJECT RESTORE GATE — PASS`

`PHASE 1.6 — LOCAL GATES PASS`

Work Core v1.0 is not production-ready yet: trusted production HTTPS, reboot proof, Telegram smoke and real-user UAT remain server-dependent.
