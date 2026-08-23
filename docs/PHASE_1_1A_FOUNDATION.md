# Phase 1.1A — Production Foundation

## Canonical production models

- People: `Employee`, `Position`, `FunctionalGroup`, `FunctionalGroupMembership`.
- Organization: `LegalEntity`, `OrgUnit`, `Location`.
- Assignment: `AssignmentTarget` and `AssignmentResolver`.
- Access: `Role`, `Permission`, `RolePermission`, `EmployeeRole`, RBAC scopes and policies.
- Operations: immutable `AuditEvent` and transactional `OutboxEvent`.

The pre-production `Company`, `Department`, `Facility` and account-level `UserRole`
models remain available to the presentation modules. They are compatibility models,
not the canonical API for new Work Core development.

## Internal API

The versioned API is mounted at `/api/internal/v1/` and contains employees,
positions, legal entities, org units, locations, functional groups, roles,
permissions and role-permission grants. All routes require authentication and
centralized `PermissionService` authorization; Django superusers retain the
technical bypass.

Business commands include:

- `POST /api/internal/v1/employees/{id}/deactivate/`
- `POST /api/internal/v1/employees/{id}/roles/`
- `POST /api/internal/v1/org-units/{id}/move/`
- `POST /api/internal/v1/functional-groups/{id}/members/`

## Initial permissions

Run `python manage.py seed_permissions`. The command is idempotent and creates
the Phase 1.1A permission catalogue without embedding AYS Group structure or
business role assignments in migrations.

## Events

Domain services create audit and outbox rows within the same database transaction.
`OutboxProcessor.process_batch(handler)` is the synchronous worker foundation;
an external broker is intentionally not required in this phase.

## Tasks Core contract

New Work Core records can persist both an `AssignmentTarget` and the Employee
returned by `AssignmentResolver`. The resolved employee is a historical snapshot;
changing a position occupant does not mutate existing work records.
