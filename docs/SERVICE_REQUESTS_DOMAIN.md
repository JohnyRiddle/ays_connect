# Service Requests Domain

Canonical production domain: `backend/service_requests`. Canonical production Tasks: `backend/work_tasks`. `backend/tasks` — legacy; new development MUST NOT use legacy Tasks.

## Catalog и формы

`ServiceCategory → Service → RequestType` формирует каталог. RequestType содержит access rules, operational task completion policy и immutable published `RequestTypeSchemaVersion`. Dynamic values валидируются единым `RequestSchemaValidator` и сохраняются snapshot-записями с key/type/label/value.

## Request Core

`ServiceRequest` имеет UUID, immutable concurrency-safe номер `REQ-*`, requester/creator, snapshot service/category/context, priority, strict status, assignment snapshots, lifecycle timestamps и optimistic `version`. Core mutations выполняются только через `ServiceRequestService`, Audit и transactional Outbox.

Lifecycle: NEW, ASSIGNED, IN_PROGRESS, WAITING_REQUESTER, WAITING_EXTERNAL, RESOLVED, CLOSED, CANCELLED. State machine запрещает произвольный PATCH статуса. Assignment использует `AssignmentTarget` и `AssignmentResolver`; routing rules детерминированы и учитывают legal entity, org unit, location и priority. Waiting, status и assignment имеют histories. Resolution отделён от close; reopen и cancellation требуют причины.

Relations поддерживают DUPLICATE_OF/RELATED_TO. `ServiceRequestTask` связывает заявку только с `work_tasks.Task`; provenance Task — `source_type=request`. Completion policy может не ограничивать resolve либо требовать terminal/completed execution tasks.

## Collaboration

`ServiceRequestComment` разделяет PUBLIC и INTERNAL, хранит revisions, mentions и soft-delete metadata. `ServiceRequestAttachment` использует Django Storage, generic attachment security pipeline, SHA-256 и protected download. `ServiceRequestWatcher` расширяет PARTICIPATING только для активного Employee. Internal collaboration всегда требует отдельное permission и не следует автоматически из request access или watcher status.

Activity Feed — permission-filtered aggregation Audit metadata, а не вторая history table. Он не раскрывает comment body, dynamic values, raw audit snapshots или факт internal activity requester-стороне. Detail summary также privacy-filtered. Collaboration не изменяет core `version`.

## Permissions и scopes

Поддерживаются OWN, PARTICIPATING, TEAM, ORG_UNIT, LEGAL_ENTITY, GLOBAL. PARTICIPATING: requester, creator, responsible employee, assigned employee или active watcher. Core permissions покрывают create/view/edit/assignment/lifecycle/task creation/admin. Collaboration permissions: comment, comment_internal, comment_moderate, attachment_add, attachment_internal, attachment_delete, watch, watcher_manage. Routing имеет отдельные view/manage permissions.

## Security и события

Все nested resources выбираются через Request из URL. Internal UUID не обходит visibility checks. PUBLIC permission нельзя повысить payload-полем до INTERNAL. Mention target обязан видеть соответствующий слой. Audit может хранить operational metadata, но activity использует allow-listed mapper. Outbox events содержат identifiers/metadata, но не form values, comment body или file content.
