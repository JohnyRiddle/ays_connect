# Phase 1.2C — Request Collaboration

Phase 1.2C завершает пользовательский collaboration-слой production Service Requests.

## Public и Internal

Комментарии и вложения имеют immutable visibility `public` или `internal`. PUBLIC доступен участникам заявки согласно `request.view`. INTERNAL требует отдельные `request.comment_internal` или `request.attachment_internal`; watcher сам по себе этих прав не получает. Скрытые записи не возвращаются как placeholder, не попадают в requester activity и не раскрываются counters.

## Comments и mentions

`ServiceRequestComment` поддерживает trim validation, revisions, `edited_at` и soft delete. Автор редактирует свой комментарий, другой пользователь — только с moderation permission. Visibility через обычный edit не меняется. Mentions задаются UUID сотрудников, дедуплицируются и разрешены только для активного Employee, который видит Request и выбранный visibility layer. Events создаются только для новых mentions и не содержат body.

## Attachments

Task и Request attachments используют общий `config.attachments` security pipeline: configurable 25 MiB limit, MIME allow-list, executable signatures, SHA-256 и scanner hook. Физический путь не содержит original filename. Download доступен только через authenticated nested endpoint после Request и visibility checks. При ошибке DB/Audit/Outbox сохранённый файл удаляется.

## Watchers

Watcher хранится исторически с soft removal и partial unique constraint для одной активной записи. Active watcher расширяет PARTICIPATING, но не requester/assignment/SLA ownership и не internal permissions. Deactivated Employee не является effective watcher.

## Activity и summary

`ServiceRequestActivitySelector` строит paginated read model из безопасных Audit metadata, сортирует по timestamp/id и ограничивает page size до 100. Raw audit values и dynamic payload не выдаются. Request detail содержит collaboration counters, task summary и permission/state-aware `available_actions`; requester не видит internal counters.

## Concurrency

Collaboration mutations не увеличивают `ServiceRequest.version`. Comment, mentions, Audit и Outbox выполняются в одной транзакции; watcher, Audit и Outbox — также. PostgreSQL tests проверяют concurrent comments и duplicate watcher race.

## State policy

Comments доступны до CLOSED включительно; CANCELLED read-only, кроме superuser override. Attachment upload разрешён до RESOLVED включительно и запрещён после CLOSED/CANCELLED. Core lifecycle нельзя изменить через collaboration payload.

## Gate

Migration `service_requests.0004` применена на чистом PostgreSQL и поверх Phase 1.2B upgrade-копии с сохранением данных. Полный итоговый gate фиксируется в `docs/CURRENT_STATE.md`.
