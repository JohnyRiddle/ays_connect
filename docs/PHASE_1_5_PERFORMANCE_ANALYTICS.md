# Phase 1.5 — Performance / Efficiency / Management Analytics

## Baseline

- Deployment checkpoint: `4f9463f feat(deployment): prepare work pilot environment`.
- PostgreSQL regression baseline: `182/182 PASS`.
- Phase 1.5 не изменяет production Task/Request/SLA architecture и не использует legacy `tasks`/`analytics` как source of truth.

## Реализованный контур

- стабильный registry из 30 метрик в категориях VOLUME/SPEED/SLA/QUALITY/DISCIPLINE/LOAD/FLOW;
- task/request/SLA facts, historical assignment attribution, waiting/deadline/reopen/reject signals;
- versioned aggregate slices и immutable scoring policy versions;
- full rebuild, Outbox-driven incremental queue, concurrent `SKIP LOCKED` worker, retry и reconciliation-safe idempotency;
- internal API: `me`, employee, org unit/employees, location, legal entity, overview и metric definitions;
- SQL-level visibility и neutral sparse-data status;
- SPA «Эффективность» переведена на production `/api/internal/v1/performance/` и объясняет ожидание, атрибуцию и размер выборки;
- performance worker добавлен в pilot и production compose.

## Quality gate — PASS

- PostgreSQL 17.11; clean test migrations и upgrade текущей pilot DB: PASS;
- backend: 231/231 PASS (49 новых Performance tests, включая 30 metric definitions, 9 aggregation cases, scoring, API/IDOR и PostgreSQL concurrent queue claim);
- `manage.py check`, migration drift, `git diff --check`: PASS;
- frontend TypeScript/Vite production build: PASS;
- synthetic scale: 100 employees, 10,000 Tasks, 10,000 Requests → 130,000 facts за 52.783 s, транзакция полностью rollback-only;
- PostgreSQL EXPLAIN: `perf_fact_emp_metric_time` Index Scan, 100 rows, execution 0.134 ms;
- post-migration backup checksum и isolated restore: PASS (`performance` migrations=2, aggregates=30);
- HTTPS readiness и SPA fallback `/tasks/...`, `/requests/...`, `/notifications/...`, `/performance/...`: HTTP 200.

`PHASE 1.5 COMPLETE`. Phase 1.6 не начата.
