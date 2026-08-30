# Phase 1.1D — Tasks Completion

## Task Templates

`TaskTemplate` stores reusable Task configuration, AssignmentTarget references,
relative planning/deadline rules and ordered links to ChecklistTemplate. It has no
Task lifecycle or collaboration data. Instantiation resolves assignments, creates a
Task snapshot, copies checklist snapshots and optionally publishes it in one database
transaction.

Deadline rules are `NONE`, `AFTER_CREATION` and `AFTER_PLANNED_START`; offsets use
calendar duration because Business Calendar belongs to SLA. Tasks retain
`source_template`, while later template edits never propagate to existing Tasks.
Deactivation also pauses active recurrence rules without deleting history.

## Recurring Tasks

`TaskRecurrenceRule` stores an iCalendar RRULE, explicit IANA timezone, start/end,
operational timestamps and error summary. Supported frequencies are HOURLY, DAILY,
WEEKLY, MONTHLY and YEARLY. SECONDLY/MINUTELY schedules are intentionally rejected.
Python dateutil handles timezone-aware recurrence calculation and DST behavior.

Each scheduled time has one `TaskOccurrence`, protected by a unique constraint on
`(recurrence_rule, occurrence_at)`. Statuses are PENDING, GENERATED, FAILED and
SKIPPED. Every generated occurrence creates a new published Task with recurrence and
template provenance; Tasks are never reset and reused.

The scheduler service generates only within the configured horizon. Defaults:

- `TASK_RECURRENCE_HORIZON_HOURS=24`
- `TASK_MAX_OCCURRENCES_PER_RULE_PER_RUN=100`
- `TASK_MAX_TOTAL_OCCURRENCES_PER_RUN=500`

Run `python manage.py generate_recurring_tasks` from cron/systemd timer. The command
contains no business logic. FAILED occurrences remain available for explicit retry.
Resume calculates the next occurrence from the current time and does not backfill the
paused interval.

## Saved and system views

`TaskSavedView` stores only an allow-listed declarative filter dictionary and ordering
field. Raw SQL, ORM expressions and unknown fields are rejected. Views are private to
their Employee owner, soft-deactivated, and a partial unique constraint permits one
active default per owner.

The Task list supports `saved_view=<uuid>` and system views:

- MY_TASKS
- CREATED_BY_ME
- WATCHING
- OVERDUE
- COMPLETED
- WITHOUT_DEADLINE

## UX support and performance

Task detail exposes permission/state-derived `available_actions`; command endpoints
still repeat every security and lifecycle check. `GET /tasks/counters/` uses one
conditional aggregate over the permission-filtered queryset. Template, recurrence,
occurrence and Saved View lists are paginated. All ordering and filter fields use
explicit allow-lists.

## Security and operations

Templates and recurrence resources are filtered by RBAC context. Occurrences are
reachable only through an accessible recurrence. Saved Views are owner-only.
Template instantiation and occurrence generation use AuditEvent and Transactional
Outbox without introducing parallel audit systems.

The accumulated PostgreSQL gate passed on PostgreSQL 17.11 on 30 August 2026. Clean
migrations and an upgrade cycle from `work_tasks 0002` to `0003` preserved an existing
Task. The complete backend suite passed 181/181; the Tasks suite passed 45/45.
Dedicated transaction tests cover concurrent numbering, optimistic locking,
occurrence idempotency and watcher creation. The gate exposed a missing-row race in
watcher creation; additions are now serialized through the stable parent Task row.
Template instantiation also has a regression test proving Task, Audit and Outbox
rollback together.
