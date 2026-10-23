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
Production publication used 41c6de4 plus this UI patch; the main build was not
deployed. The feedback owner reversibly disabled its old launcher before the UI
switch. Feedback remains pending and requires a new coordinated release baseline.

Production accepted at 2026-10-23 05:10 UTC: frontend
`6eaf7995acd71951c4bb05341b5f41bcf3a2f900`, backend unchanged
`41c6de4c4b724238d9ab9f4c043dc2d6828debf2`. The exact production-only build also
passed 54 synthetic browser tests. Public HTTPS: 24 checks across both domains,
including every new asset hash and backend health. Public browser: four
desktop/mobile light/dark checks with synthetic API data, zero real HTTP writes;
feedback UI absent. All ten existing core container IDs/images remained unchanged,
including seven healthy app services. No DB commands or migrations were executed.

The 58-file old frontend archive was restored locally and hash-compared, then
stored on the server and verified by byte-for-byte roundtrip. All old assets were
retained; the old image index hash matches the backup for rollback. Release directory:
`/home/ivan/ays-task-trash-style-6eaf7995acd7`. Only `frontend_assets.image` changed
in compose; existing metadata was updated after smoke, retaining backend values.

- New frontend image: `sha256:d339fab8a73d6f270a4cee633773865f710d373a81dd75b0f6602b3f33931bf6`.
- Old index SHA256: `501e1e5a19a192874b4dbbd8bd327820b61c767ca4af9a4a4148296ad8c6e804`.
- New index SHA256: `c974c353e0c77f3c369674cfeeea9bb113eccc40dc02de2664be6cbc3a895ba6`.
- Backup SHA256: `202c6f71924a99a8ce58ffcadca1704419fea72bedaf9376cb4d2ca94573359b`.

Full baseline/candidate manifests, original stack/wrapper, restore and browser
evidence are retained in the isolated task's `ui-release-evidence/` directory.
GitHub has no configured workflow/status checks; local checks are the validation.

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
