# Phase 1.2A — Service Catalog

## Назначение

Модуль `service_requests` описывает управляемый каталог корпоративных услуг и формы будущих заявок. Lifecycle заявок, маршрутизация, SLA, назначения и связь с задачами в этот этап не входят.

## Каталог

Иерархия строится как `ServiceCategory → Service → RequestType`. Категории используют adjacency list (`parent`); сервисный слой запрещает self-parent и перенос категории в собственное поддерево. Категории, сервисы и типы имеют явное поле `position` и мягкую деактивацию.

`Service` может содержать информационные связи с `OrgUnit`, `FunctionalGroup`, `LegalEntity` и `Location`. Эти связи не выполняют автоматическое назначение.

## Типы заявок и доступ

`RequestType.code` — уникальный стабильный технический ключ. Доступность формы требует одновременно:

- активных категории, сервиса и типа;
- опубликованной схемы;
- активного Employee с permission `request.create`;
- совпадения хотя бы одного access rule, если правила существуют.

Поддерживаются правила `GLOBAL`, `LEGAL_ENTITY`, `ORG_UNIT`, `LOCATION`, `ROLE`. При отсутствии правил тип доступен всем активным сотрудникам с `request.create`.

## Динамические поля

Поддержаны типы `TEXT`, `TEXTAREA`, `INTEGER`, `DECIMAL`, `BOOLEAN`, `DATE`, `DATETIME`, `CHOICE`, `MULTI_CHOICE`, `EMPLOYEE`, `ORG_UNIT`, `LEGAL_ENTITY`, `LOCATION`, `FILE`.

Для текста поддержаны `min_length`/`max_length`, для чисел — `min_value`/`max_value`. Entity-поля хранят UUID. Choice-поля используют нормализованные `RequestFieldOption`; snapshot содержит собственную копию вариантов.

Условная видимость задаётся одним `visible_if` с оператором `EQUALS` или `NOT_EQUALS` относительно поля `CHOICE`/`BOOLEAN`. Невидимые значения отбрасываются, а обязательность применяется только к видимым полям.

## Версионирование схемы

Администратор редактирует live draft в `RequestFieldDefinition` и `RequestFieldOption`. `publish-schema` атомарно блокирует RequestType, проверяет конфигурацию, создаёт очередной `RequestTypeSchemaVersion`, переключает `current_schema_version`, записывает Audit и Outbox.

Snapshot содержит ключ, подпись, тип, обязательность, позицию, default, config и варианты. Опубликованные версии неизменяемы и не удаляются. Будущая Request Phase 1.2B должна ссылаться на конкретную версию, а не на live draft.

## Валидация

`RequestSchemaValidator` валидирует payload только против выбранного snapshot. Проверяются required, длины, числовые границы через Decimal, ISO date, timezone-aware datetime, варианты выбора, отсутствие дублей, UUID и существование production-сущностей, базовые ограничения legal entity/org unit и условные поля.

## Permissions

- `service_catalog.view`
- `service_catalog.manage`
- `request_type.view`
- `request_type.manage`
- `request_type.publish`
- `request.create`

## API

Административные ресурсы:

- `/api/internal/v1/service-categories/` — create/list/detail/PATCH/move/deactivate;
- `/api/internal/v1/services/` — create/list/detail/PATCH/deactivate;
- `/api/internal/v1/request-types/` — create/list/detail/PATCH/deactivate;
- `/request-types/{id}/fields/` и вложенные options;
- `/request-types/{id}/access-rules/`;
- `/request-types/{id}/publish-schema/`.

Пользовательские представления:

- `/api/internal/v1/service-catalog/` — очищенное дерево доступных категорий, сервисов и типов;
- `/api/internal/v1/request-types/{id}/form-schema/` — текущий опубликованный typed contract с обязательной проверкой доступа и защитой от IDOR.

## Audit и события

Audit фиксирует изменения категорий, сервисов, типов, полей и публикацию. Outbox публикует integration-relevant события `service.created`, `service.updated`, `request_type.created`, `request_type.updated`, `request_type.deactivated`, `request_type.schema_published`.

## Ограничения этапа

Тип `FILE` пока описывает только контракт поля. Фактические вложения появятся вместе с Request в Phase 1.2B и должны переиспользовать storage abstraction Tasks. Условная логика намеренно ограничена одним условием без формул, скриптов и AND/OR-деревьев.
