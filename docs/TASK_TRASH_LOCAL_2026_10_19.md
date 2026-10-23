# Reversible task deletion

## 2026-10-23: secondary trash filter

The deleted-only checkbox now follows the main filters and uses a compact native
16px control with secondary text, a 44px label target and explicit keyboard focus.
It no longer inherits the full-width, 42px-high text-field presentation. Existing
deleted query, pagination reset, routes, restore actions and permissions are unchanged.

Local validation on main a2c4265: TypeScript/Vite build and 54 synthetic browser
scenarios pass, including light/dark themes at 1280/390px, Tab/Space, label click,
pagination reset, trash/restore and viewer restrictions. Text contrast against the
page token is 6.96:1 light and 10.99:1 dark. This is not production acceptance.
Production publication must use 41c6de4 plus this UI patch until feedback PR24 is
released; do not deploy a main build or invalidate its pending release launcher.

Prepared against e70f79695634198ad197361fe7d26b3763148a80.

The task action menu offers deletion with confirmation. The deleted-only list
provides restoration. Discussion, files, history, status, assignment, project/stage
links and parent references remain intact. There is no hard deletion or cascade.

The API uses existing scoped task.cancel / task.reopen permissions and task
versions. Project-linked tasks additionally require project visibility, task-link
management permission and the current project version. No roles or grants change.
Task and project changes are transactional and serialize with existing project
operations. Audit and outbox events record trash/restore.

Active and final tasks can enter trash. Parents with undeleted children cannot.
Deleted tasks are excluded from active lists, counters, overdue processing,
project progress/completion predicates and inherited deadline propagation.
Mutating task, discussion and approval commands reject deleted tasks, including
stale service callers. Historical records remain accessible under existing RBAC.
New task notifications are suppressed; existing deliveries and recurrence rules
remain independent. Telegram transport is unchanged.

Restoration validates the current project, stage, parent and eligible participants.
Closed or archived projects never reopen implicitly. Active children cannot be
restored into a deleted or final parent. Inherited due dates use the current
project deadline, as explained in the confirmation; manual deadlines must still
fit the project. Any deadline adjustment receives a deadline-history entry.
The work status remains unchanged.

Validation: 279 PostgreSQL tests across work_tasks, projects, notifications and
performance pass, including project-link/history preservation, parent protection,
version conflicts and a concurrent project-edit/trash test. Fifty desktop/mobile
browser scenarios pass, including nine trash scenarios. Those browser tests use
synthetic API responses and are not production acceptance. TypeScript/Vite build
and migration drift checks pass.

Migration work_tasks.0013_task_deleted_at adds one nullable timestamp column and
its index. It changes no existing task values. Release gates require a scoped,
encrypted task/migration backup, restore verification, rehearsal of the exact
migration, and before/after preservation checks. Rollback returns to prior images
and frontend index while retaining the compatible nullable column; it must not
restore an old database over live writes.

No real task may be deleted for smoke testing. Production acceptance is limited
to read-only API/browser checks, confirmation cancellation, health, exact source
version and asset hashes. Deployment results are recorded separately.
