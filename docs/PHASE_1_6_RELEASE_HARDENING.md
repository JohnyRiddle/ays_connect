# Phase 1.6 — Work Core Release Hardening

Initial checkpoint: `0068d12 feat(performance): complete work analytics and efficiency domain`.

Phase 1.6 соблюдает functional freeze: новые lifecycle, KPI, каналы и крупные возможности не добавляются. Разрешены только security, correctness, recovery, observability, deployment и UX stabilization.

## RC strategy

`main → hardening changes → RC1 → server pilot validation → RC2 if needed → v1.0`. Централизованная версия RC: `1.0.0-rc1`; backend отдаёт её в health/system status, frontend получает build metadata.

## Реализованный hardening

- login rate limit, neutral authentication errors, disabled Employee enforcement для login/JWT refresh;
- refresh rotation blacklist и logout token revocation;
- correlation `X-Request-ID`, безопасный protected system status;
- worker heartbeat/stale status для recurrence, schedule, SLA, escalation, notifications и performance;
- Outbox retry metadata, bounded attempts, poison/abandoned-event reconciliation;
- performance abandoned-claim recovery и расширенный rebuild output;
- executable upload signature/double-extension blocking;
- safe production env template, SPA cache headers и explicit RC metadata.
- production Compose без demo seed, с Caddy-only public ports, полным worker inventory и backup service;
- dependency remediation: Django 5.2.17 и SimpleJWT 5.5.1, backend/frontend audits clean;
- PostgreSQL regression 251/251, high-contention numbering, restart/persistence and synthetic performance gates.

## Обнаруженные release blockers

- текущая SPA остаётся legacy-клиентом `/api/v1/tasks/` и не реализует production `work_tasks` / `service_requests` user flows;
- pilot data set не содержит Task/Request/SLA/Notification/attachment samples для полного domain-level restore и checksum proof;
- browser UX/responsive smoke нельзя закрыть до production SPA; локальный CA также не является trusted public TLS.

Поэтому текущий статус — `PHASE 1.6 — LOCAL GATES BLOCKED`, production gates — `PENDING`. Functional freeze не позволяет скрытно превратить hardening в разработку нового крупного frontend слоя.

## Accepted deployment-check classification

`drf_spectacular.W001/W002` are pre-existing OpenAPI introspection diagnostics for dynamic APIViews and duplicate serializer component names. They are explicitly silenced from system checks, not hidden as security warnings: runtime serializers/permissions and generated application behavior remain covered by tests. Full schema cleanup is post-v1 documentation debt. Django `security.*` deployment warnings remain enabled and must pass under production environment values.

Фактические gate results ведутся в `WORK_CORE_V1_RELEASE_CHECKLIST.md`. Статус PRODUCTION READY запрещён до устранения local blockers, server hostname, trusted TLS, host reboot, real Telegram и acceptance personas.
