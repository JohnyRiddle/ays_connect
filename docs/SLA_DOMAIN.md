# SLA Domain

## Границы домена

`sla` хранит конфигурацию календарей/политик и runtime SLA. Он использует production-сущности `organizations`, `employees` и `service_requests`, но не добавляет SLA runtime-поля в `ServiceRequest` и не зависит от legacy `tasks`.

## Версионирование

Редактируемые `BusinessCalendar` и `SLAPolicy` являются черновиками. Publish выполняется в транзакции и создаёт immutable `BusinessCalendarVersion` или `SLAPolicyVersion`. Политика BUSINESS_TIME ссылается именно на опубликованную версию календаря, поэтому последующее редактирование календаря не меняет исторические нормативы.

Версии нельзя изменять или удалять через модель и Admin. Publish также пишет Audit и Outbox; ошибка любого шага откатывает всю транзакцию.

## Расчёт рабочего времени

`BusinessTimeCalculator` принимает timezone-aware datetime и опубликованный календарь/его версию. Интервалы вычисляются в локальной IANA timezone календаря, а длительность считается по UTC, что сохраняет корректное фактическое время на переходах DST.

Поддерживаются:

- несколько рабочих интервалов в день и обеденные разрывы;
- полностью нерабочие даты;
- рабочий день по обычному расписанию;
- пользовательские интервалы конкретной даты;
- поиск следующего рабочего момента, прибавление и подсчёт рабочего времени.

## Назначение политики

Активные правила сопоставляются по request type, service, priority, legal entity, org unit и location. Побеждает правило с большим числом заполненных совпавших полей; затем меньшее значение `order`. Два равноценных лучших правила считаются ошибкой конфигурации, а не выбираются случайно. Resolver возвращает только опубликованную версию, действующую в указанный момент.

## Runtime и resolution cycles

При регистрации заявки resolver фиксирует immutable policy/calendar context в единственном `SLAInstance`. Response metric существует один раз за жизнь заявки. Resolution создаётся как последовательность cycles: первый вместе с instance, каждый следующий при reopen и с полной duration опубликованной policy version.

Lifecycle request транзакционно вызывает runtime hook: start достигает response, waiting создаёт pause, resume закрывает pause и пересчитывает остаток, resolve достигает текущий cycle, cancel отменяет активные metrics. Reconciliation повторяет эти операции idempotently при восстановлении.

## Pause accounting

Elapsed-time исключает wall-clock duration закрытых pauses. Business-time считает consumed/remaining только через immutable calendar version. При resume materialized deadline воспроизводится как `resume + remaining effective duration`; pause history хранит и elapsed, и business seconds.

## Warnings, breaches и evaluator

`SLAThresholdEvent` уникален для пары metric/threshold, поэтому warning каждого resolution cycle независим и idempotent. Breach timestamp равен точному effective deadline, даже если worker запущен позже. Late achievement завершает metric статусом `ACHIEVED`, не стирая `breached_at`.

`process_sla` выполняет evaluator batches с row locking/`SKIP LOCKED`; режим `--reconcile` восстанавливает runtime из canonical request timestamps и истории.

## Следующая фаза

Escalation policies, доставка уведомлений и автоматические breach actions должны внедряться отдельной фазой поверх runtime events.
