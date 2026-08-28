# Phase 1.3B — SLA Runtime

Дата реализации: 28.08.2026.

## Реализовано

Runtime SLA размещён в существующем `backend/sla` и транзакционно подключён к production lifecycle `ServiceRequest`.

- один `SLAInstance` на заявку с immutable ссылками на policy/calendar version;
- отдельная response metric и cycle-aware resolution metrics;
- вычисление elapsed-time и business-time deadlines;
- idempotent response/resolution achievement, cancellation и reopen;
- pause periods для WAITING_REQUESTER/WAITING_EXTERNAL с partial unique constraint;
- при resume elapsed deadline продлевается на wall-clock pause, а business deadline строится заново из оставшегося рабочего времени;
- warning threshold history, breach detection и сохранение late achievement после breach;
- Audit и transactional Outbox для runtime transitions;
- idempotent evaluator и portable `process_sla` с batching/`SKIP LOCKED`;
- reconciliation missing instance/achievement/pause/stale pause/reopen cycle;
- request SLA summary, status/history endpoints и SQL-level list filters.

## Runtime model

`SLAInstance` владеет response metric и последовательностью `SLAResolutionCycle`. Каждый resolution cycle имеет собственную metric, deadline, thresholds и pause periods. Reopen создаёт новый cycle с полной resolution duration; response metric не перезапускается.

Metric status после позднего достижения становится `ACHIEVED`, а `breached_at` сохраняется как независимый исторический факт.

## Worker

```bash
python manage.py process_sla --batch-size 100
python manage.py process_sla --batch-size 100 --reconcile
```

Worker использует один injected timestamp на запуск, row locks и PostgreSQL `SKIP LOCKED`, когда он доступен. Ошибка одного instance логируется только с instance/request IDs и не делает обработку остальных невоспроизводимой.

## API

- `GET /api/internal/v1/requests/{id}/sla/`;
- `GET /api/internal/v1/requests/{id}/sla/history/`.

Оба endpoint наследуют SQL-level доступ к родительской заявке. При отсутствии SLA возвращается `200 {"has_sla": false}`.

## Границы

В фазу не входят escalation policies, уведомления, автоматические breach actions и performance scoring.

## Quality gate

PostgreSQL 17.11: clean migration PASS, upgrade `sla.0001 → 0002` PASS, SLA tests 18/18, полный backend suite 139/139. В gate включены 8 concurrent creation attempts, concurrent evaluator, partial unique active pause и transactional rollback Audit/Outbox.
