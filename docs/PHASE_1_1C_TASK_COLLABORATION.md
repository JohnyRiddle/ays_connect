# Phase 1.1C — Task Collaboration

## Scope and compatibility

The collaboration layer extends `work_tasks.models.Task`. Legacy `tasks`, legacy
comments, attachments and `checklists` remain unchanged and are not used by the
production API.

Collaboration mutations do not increment `Task.version`: they have independent
database constraints and row locks. Core lifecycle mutations retain optimistic
versioning. Checklist completion and Task completion serialize on the same Task row,
so completion always reads current required-item state.

## Comments and mentions

Comments belong to Employee authors, reject whitespace-only bodies and use soft
deletion. Editing stores the previous body in `TaskCommentRevision`. The API accepts
explicit Employee UUID mentions; inactive or inaccessible employees are rejected.
Only newly added mentions create `task.comment_mentioned` events. Deleted comment
text remains available for corporate audit but is never returned by the user API.

Internal comments require `task.comment_internal` and are removed from Activity Feed
and comment collections for users without that permission.

## Attachments

Attachments use Django Storage and paths shaped as
`tasks/<task UUID>/<attachment UUID>/file`. The original filename is metadata only.
Uploads enforce a configurable 25 MiB default, MIME allow-list, empty-file rejection,
basic executable signature rejection and SHA-256 checksum calculation.

`AttachmentScanner` is the extension point for future ClamAV integration and is a
NoOp in this phase. Download always resolves the parent Task through its permission-
filtered queryset. Deletion is logical; physical retention cleanup is intentionally
deferred. If the SQL transaction fails after storage upload, the stored object is
removed immediately.

Settings:

- `TASK_ATTACHMENT_MAX_SIZE`
- `TASK_ATTACHMENT_ALLOWED_TYPES`

## Watchers

Watcher history is soft-removed and a partial unique constraint prevents duplicate
active watchers. Self watch uses `task.watch`; managing another employee uses
`task.watcher_manage`. Active watchers now participate in `PARTICIPATING` Task scope
without becoming responsible or executor.

## Checklists

`ChecklistTemplate` and ordered template items are separate from `TaskChecklist` and
its items. Applying a template copies a snapshot, so later template changes never
alter existing Tasks. Manual checklists use the same instance model.

Completion records Employee and timestamp; uncompletion clears both. Incomplete
required items block both direct completion and submission to review with
`task_checklist_incomplete`. Logical checklist removal requires management permission.

## Activity Feed

`GET /api/internal/v1/tasks/{id}/activity/` is an offset-paginated read model over
existing AuditEvent/domain histories. It does not create another universal activity
table. Ordering is stable by `(timestamp DESC, UUID DESC)`, page size is capped at
100, internal comments are permission-filtered and deleted bodies are never exposed.

## API

- `GET/POST tasks/{id}/comments/`
- `PATCH/DELETE tasks/{id}/comments/{comment_id}/`
- `GET/POST tasks/{id}/attachments/`
- `GET tasks/{id}/attachments/{attachment_id}/download/`
- `DELETE tasks/{id}/attachments/{attachment_id}/`
- `POST/DELETE tasks/{id}/watch/`
- `GET/POST tasks/{id}/watchers/`
- `DELETE tasks/{id}/watchers/{employee_id}/`
- Task checklist list/create, template application, item editing and completion routes
- `GET/POST/PATCH /api/internal/v1/checklist-templates/`

Every nested resource is resolved together with the permission-filtered Task from the
URL, preventing cross-task UUID access.

## Permissions and events

Permissions added: `task.comment`, `task.comment_internal`,
`task.comment_moderate`, `task.attachment_add`, `task.attachment_delete`,
`task.watch`, `task.watcher_manage`, `task.checklist_manage`,
`task.checklist_complete`, `checklist_template.view` and
`checklist_template.manage`.

Collaboration mutations create AuditEvent and OutboxEvent in one transaction. Events
cover comments, mentions, attachments, watchers, checklists and item state changes.

## Deployment caveat

SQLite validates functionality and migration compatibility, but PostgreSQL remains a
mandatory pre-deployment gate for partial constraints and concurrent row locking.
