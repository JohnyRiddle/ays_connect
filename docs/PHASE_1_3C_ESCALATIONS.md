# Phase 1.3C — Escalation Policies / Runtime / Actions

Дата реализации: 28.08.2026. Исходный checkpoint: `6cd2169`.

## Реализовано

Escalation Engine добавлен в существующий `backend/sla` как отдельный слой поверх фактов SLA runtime:

- draft escalation policies, rules/actions и immutable published snapshots;
- version-safe binding `SLAPolicyVersion → EscalationPolicyVersion`;
- один `EscalationInstance` на SLA instance;
- cycle-aware executions с DB idempotency identity;
- ON_WARNING, ON_BREACH и elapsed AFTER_BREACH_DURATION;
- materialized delayed schedules с cancellation history;
- notification intents `notification.requested` без delivery subsystem;
- target resolution для requester/executor/responsible/managers/AssignmentTarget;
- ADD_WATCHER, monotonic CHANGE_PRIORITY и controlled REASSIGN через production Request services;
- worker `process_escalations`, reconciliation, row locks и PostgreSQL `SKIP LOCKED`;
- safe Request status/history API, configuration API, binding API и preview;
- Audit, transactional Outbox, permissions и read-oriented Admin.

## Trigger semantics

ON_WARNING потребляет существующий `SLAThresholdEvent` и не вычисляет SLA повторно. ON_BREACH использует canonical `metric.breached_at`. AFTER_BREACH_DURATION создаёт schedule на `breached_at + delay_seconds`; post-breach delay всегда elapsed time. Achievement/cancellation отменяют ещё не выполненные delayed schedules.

Resolution executions привязаны к конкретной metric/cycle. Поэтому breach после reopen создаёт независимую историю, не изменяя первый cycle.

## Action semantics

- REQUEST_NOTIFICATION создаёт по одному безопасному Outbox intent на фактически resolved Employee;
- ADD_WATCHER использует production watcher service и остаётся idempotent;
- CHANGE_PRIORITY использует canonical request priority ordering и не понижает priority;
- REASSIGN использует AssignmentResolver и production reassignment service; terminal/unresolved cases контролируемо пропускаются.

Каждое action выполняется в собственной транзакционной границе. Immutable execution хранит snapshots правила, action и resolved recipients.

## API и worker

- `/api/internal/v1/sla/escalation-policies/`;
- `/api/internal/v1/sla/escalation-policy-versions/`;
- `/api/internal/v1/sla/escalation-bindings/`;
- `POST /api/internal/v1/sla/escalation-preview/`;
- `GET /api/internal/v1/requests/{id}/escalations/`;
- `GET /api/internal/v1/requests/{id}/escalations/history/`.

```bash
python manage.py process_escalations --batch-size 100
python manage.py process_escalations --batch-size 100 --reconcile
```

## Граница Phase 1.4

Telegram/email/push, delivery attempts, templates, preferences и provider retries не реализуются. `notification.requested` является стабильным integration contract следующей фазы.

## Quality gate

PostgreSQL 17.11: clean migration PASS, upgrade `sla.0002 → 0003` PASS, escalation/SLA tests 33/33, полный backend suite 154/154. Concurrency и E2E actions PASS.
