# AYS Connect Production Tasks Domain

> Canonical production Task: `work_tasks.models.Task`
>
> Legacy MVP module: `tasks`
>
> New production development MUST NOT use legacy tasks models.

## Architecture

The production domain is a modular-monolith Django app built on People Core,
Organization, AssignmentTarget, RBAC scopes, AuditEvent and Transactional Outbox.

TaskTemplate and recurrence occurrences create immutable Task snapshots. Task is the
work obligation and owns lifecycle state, assignment snapshots, deadlines, waiting,
review, subtasks and optimistic versioning. Collaboration adds comments, revisions,
mentions, protected attachments, watchers and snapshot checklists. Activity Feed is a
permission-aware read model over existing audit/domain histories.

## Lifecycle and assignment

The strict state machine is DRAFT → OPEN → IN_PROGRESS, with WAITING and REVIEW
branches, final COMPLETED/CANCELLED states and explicit reopen. Every lifecycle
mutation locks and version-checks Task, writes specialized history, AuditEvent and
OutboxEvent atomically.

Responsible and executor each retain both AssignmentTarget intent and resolved
Employee snapshot. Position or group membership changes never reassign historical
Tasks. `initial_due_at` is captured at publish and deadline changes have their own
history.

## Collaboration

Comments are Employee-authored, revisioned and soft-deleted. Mentions use explicit
Employee UUIDs. Attachments use Django Storage, protected download, checksum and
logical deletion. Active watchers extend PARTICIPATING scope. Required checklist
items block completion; templates are copied as snapshots.

## Templates and schedules

TaskTemplate stores relative configuration, assignment targets and ordered checklist
templates. Standard timezone-aware iCalendar RRULE creates idempotent TaskOccurrence
records. Failures are retained for retry; pause/resume never performs implicit
backfill; configurable limits prevent runaway batches.

## Access, API and operations

RBAC combines OWN, PARTICIPATING, TEAM, ORG_UNIT, LEGAL_ENTITY and GLOBAL scopes.
Selectors filter SQL querysets before serialization, including nested resources.
Internal API lives under `/api/internal/v1/` and supplies pagination, filters, search,
saved/system views, available actions and counters.

All business mutations use service-layer transactions, centralized permission policy,
AuditService and Outbox. Hard deletion of production Tasks is prohibited.

## Deployment gate

The accumulated Tasks gate passed on PostgreSQL 17.11 on 30 August 2026: clean and
upgrade migrations, 45/45 Tasks tests and 181/181 backend tests. PostgreSQL transaction
tests verify concurrent numbering, optimistic locking, watcher uniqueness and
recurrence idempotency; rollback tests cover Task/Audit/Outbox atomicity. Concurrent
watcher creation is serialized by locking the parent Task before checking the partial
unique constraint. Production file policy should still connect the existing scanner
hook to malware scanning where required.
