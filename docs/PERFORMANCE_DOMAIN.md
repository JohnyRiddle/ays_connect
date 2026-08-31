# Performance domain

`backend/performance` — производный read/aggregation domain. Он читает только канонические `work_tasks`, `service_requests`, `sla` и их истории. Запись в канонические сущности из Performance запрещена.

## Семантика

- Все интервалы имеют вид `[from, to)` и явно содержат IANA reporting timezone.
- Activity-метрики относятся к моменту события, cohort-метрики — к завершённым в периоде сущностям, snapshot-метрики — к текущему состоянию.
- Атрибуция поддерживает роли `RESPONSIBLE`, `EXECUTOR`, `REQUESTER`, `REVIEWER` и восстанавливается из assignment history на момент события.
- Ожидание заявителя/внешней стороны хранится отдельно. Переназначение закрывает прежний интервал ответственности; метрика не превращает всю просрочку в ответственность нового исполнителя.
- Отсутствие выборки — `no_data`/`insufficient_data`, а не нулевой результат.

## Хранение и пересчёт

`PerformanceFact` — воспроизводимая проекция канонического события с историческим organizational context. `PerformanceAggregate` — версионируемый срез по субъекту, периоду, timezone и metric code. Уникальные ключи делают rebuild идемпотентным.

Outbox не захватывается и не помечается Performance worker-ом: `enqueue_performance` создаёт дедуплицированную работу по `event_id`, а `process_performance` захватывает очередь через PostgreSQL `SELECT … FOR UPDATE SKIP LOCKED`. Full rebuild выполняется командой:

```bash
python manage.py rebuild_performance --from 2026-08-01 --to 2026-09-01 --timezone Asia/Novosibirsk
```

Scoring policies версионируются и после публикации immutable. Индекс 0–100 возвращается только при достаточной выборке и всегда содержит объяснение компонентов.

## Security

Self endpoint доступен сотруднику. Чужие employee/dimension endpoints сначала ограничиваются SQL queryset из `EmployeeRole`/`RolePermission`; недоступные UUID возвращают 404, что закрывает IDOR. Scope: own/team/org unit/legal entity/global.
