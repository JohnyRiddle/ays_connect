# Phase 1.2B — Service Request Core

Production-домен заявок реализован в существующем `backend/service_requests`. Legacy `backend/tasks` не используется; заявки связываются только с `work_tasks.Task` через явную модель `ServiceRequestTask`.

## Модель и историческая стабильность

`ServiceRequest` хранит UUID, immutable номер `REQ-000001`, тип и опубликованную schema version, requester/creator, snapshot service/category и организационного контекста, priority/status, назначения, lifecycle timestamps и `version`. Валидированные динамические значения нормализованы в `ServiceRequestFieldValue` вместе с key/type/label, поэтому изменение живого каталога не меняет старую заявку.

## Lifecycle

Переходы централизованы в `ServiceRequestStateMachine`, а mutations — в `ServiceRequestService`. Статус нельзя менять PATCH-запросом. Все mutations требуют ожидаемую `version`; stale write возвращает `409 request_version_conflict`. Waiting, assignment и status имеют отдельные histories. Resolution требует комментарий, cancellation и reopen — причину.

## Routing и assignment

`RequestRoutingRule` выбирается по RequestType, legal entity, org unit, location и priority с явным `order`. Равные лучшие правила дают `request_routing_ambiguous`; отсутствие route оставляет заявку в NEW с `routing_unresolved=true`. Target разрешается существующим `AssignmentResolver`, а target и фактический employee сохраняются одновременно.

## Tasks

`ServiceRequestTaskService` создаёт production Task вручную или из `TaskTemplate`, устанавливает provenance `source_type=request`, связывает сущности и пишет Audit/Outbox в одной транзакции. Operational policy RequestType поддерживает NONE, ALL_EXECUTION_TASKS_TERMINAL и ALL_EXECUTION_TASKS_COMPLETED. Отмена заявки не изменяет связанные задачи.

## API и безопасность

Основной endpoint: `/api/internal/v1/requests/`. Доступны list/create/detail/patch, lifecycle actions, `/tasks/` и `/history/`. List использует SQL-level scope filtering; detail и nested actions работают через тот же queryset, предотвращая IDOR. Routing rules доступны под `/request-types/{id}/routing-rules/`.

Permissions: `request.create`, `request.create_for_others`, `request.view`, `request.edit`, `request.assign`, `request.reassign`, `request.start`, `request.wait`, `request.resolve`, `request.close`, `request.reopen`, `request.cancel`, `request.task_create`, `request.admin`, `request_routing.view`, `request_routing.manage`.

## Границы фазы

SLA calculations, timers, notification delivery, comments, attachments, watchers, public API и сложный BPM/rule engine не реализуются в этой фазе. В события не помещаются значения динамической формы.

## PostgreSQL quality gate

27.08.2026 gate выполнен на PostgreSQL 17.11: все миграции применены на чистой БД, затем `0003` проверена поверх `pg_dump/pg_restore` клона pre-1.2B schema с существующим RequestType. Полный backend suite: 111 тестов. PostgreSQL-only integration suite проверяет конкурентную нумерацию, routing/create, optimistic assignment locking и rollback Request → Task при ошибках Audit/Outbox.
