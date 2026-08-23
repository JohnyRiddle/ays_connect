# Phase 1.1B — Tasks Core

## Compatibility strategy

Production Tasks live in the `work_tasks` Django app and are exposed at
`/api/internal/v1/tasks/`. The existing `tasks` app remains the presentation MVP;
its tables, data, routes and integrations are not migrated or deleted by this phase.
New Work Core development must import `work_tasks.models.Task`.

## Task model

The production Task uses a UUID primary key and an immutable human number such as
`TASK-000001`. Numbers are allocated by a locked database counter rather than
`MAX(number) + 1`. A Task references only production `Employee`, `AssignmentTarget`,
`OrgUnit`, `LegalEntity` and `Location` entities.

Both assignment intent and its historical resolution are stored:

- `responsible_target` + `responsible_employee`;
- `executor_target` + `executor_employee`.

Changing a Position or FunctionalGroup later does not modify existing Tasks.

## State machine

```text
                     ┌─────────────┐
                     │    DRAFT    │
                     └──────┬──────┘
                            │ publish
                            ▼
                     ┌─────────────┐
                     │    OPEN     │
                     └──────┬──────┘
                            │ start
                            ▼
                   ┌─────────────────┐
             ┌────►│   IN_PROGRESS   │◄────┐
             │     └───────┬─────────┘     │
             │             │               │
          resume          pause          reject
             │             │               │
             │             ▼               │
             │        ┌─────────┐      ┌────────┐
             └────────│ WAITING │      │ REVIEW │
                      └─────────┘      └───┬────┘
                                          │ accept
                                          ▼
                                    ┌───────────┐
                                    │ COMPLETED │
                                    └─────┬─────┘
                                          │ reopen
                                          └──────► IN_PROGRESS
```

`CANCELLED` is reachable from DRAFT, OPEN, IN_PROGRESS, WAITING and REVIEW.
All other transitions are rejected by `TaskStateMachine`; status is read-only in PATCH.

## Deadlines and waiting

`initial_due_at` is captured once during publish. Later changes use the deadline
business command and create `TaskDeadlineHistory`. Waiting creates one active
`TaskWaitingPeriod`; resume or cancellation closes it. Overdue is calculated and
is not represented by an extra status.

## Acceptance and subtasks

Acceptance policies are `NONE`, `AUTHOR` and `RESPONSIBLE`. Completion without
acceptance is final; otherwise it creates a review submission. Reject returns the
Task to work and requires a reason. `ALL_CHILDREN_COMPLETED` blocks completion while
an active child exists. Parent cycles are rejected by the service layer and database
self-parent constraint.

## Concurrency and atomicity

Every mutation locks the Task and verifies the supplied positive `version`. A stale
request returns HTTP 409 with `task_version_conflict`. Task mutation, domain history,
AuditEvent and OutboxEvent are committed in one transaction with one correlation ID.

## Permissions

Tasks use the existing RBAC scopes: OWN, PARTICIPATING, TEAM, ORG_UNIT,
LEGAL_ENTITY and GLOBAL. PARTICIPATING includes author, responsible employee and
executor employee. `TaskSelector.visible_to()` applies access in SQL so inaccessible
Tasks never enter list or detail querysets.

Run `python manage.py seed_permissions` to add all `task.*` permissions.

## API

Base route: `/api/internal/v1/tasks/`.

- `GET`, `POST`, `GET {id}`, `PATCH {id}`
- `POST {id}/publish/`, `start/`, `pause/`, `resume/`
- `POST {id}/complete/`, `accept/`, `reject/`
- `POST {id}/reopen/`, `cancel/`
- `POST {id}/reassign/`, `deadline/`

PATCH accepts only safe descriptive/context fields and the expected version.
Lifecycle, assignment, deadline and immutable fields are changed only by commands.
