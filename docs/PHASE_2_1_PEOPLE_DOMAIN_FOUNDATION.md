# Phase 2.1 — People Domain Foundation

## Architecture

Phase 2.1 extends the existing `employees.Employee`; no parallel Person model exists. `Employee` remains organizational identity and may exist without an authentication `User`.

The append-only `employees.0007` migration adds:

- immutable, concurrency-safe `EMP-*` numbering backed by a locked sequence row;
- employee avatar and work contacts;
- historical `EmployeeAssignment` with multiple simultaneous assignments and one active primary invariant;
- historical `EmployeeManagerAssignment` with one active manager, self-reference constraint and service-level transitive cycle protection;
- data migration of existing Position/OrgUnit/LegalEntity/Location and manager fields into initial history rows.

Legacy direct fields remain compatibility/read-model fields for Work, RBAC and existing APIs. Phase 2.1 does not remove or rewrite them.

## Lifecycle

The service layer owns employee creation/profile updates, primary assignment replacement, manager changes, termination and reactivation. Termination atomically closes active assignments, manager relationships, group memberships and invitations, blocks the linked User, and writes Audit and Outbox records. Reactivation does not restore previous access or organizational relationships.

## PostgreSQL 17.11 gates

- clean migration: PASS;
- two independent 0006 → 0007 upgrade rehearsals with legacy data: PASS;
- employee number concurrency: PASS;
- primary assignment concurrency: PASS;
- manager change concurrency: PASS;
- termination vs assignment: PASS;
- termination vs invitation/account lifecycle: PASS;
- full backend regression: 276/276 PASS on PostgreSQL.

## Scope boundary

Organization/team UI, responsibilities, People Workspace, Work/Performance profile tabs, 10k directory benchmark and complete browser E2E remain in Phase 2.2–2.5 and were not started.
