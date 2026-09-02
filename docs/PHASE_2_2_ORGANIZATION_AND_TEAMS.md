# Phase 2.2 — Organization & Teams

## Architecture

`organizations.OrgUnit` remains the only formal hierarchy. It now has typed units, lifecycle/status, validity, ordering, metadata and optimistic versioning. Parent changes and closure use `OrgUnitService`; physical deletion remains protected.

`employees.Team` is the collaboration/project grouping domain. It does not replace EmployeeAssignment or OrgUnit. `FunctionalGroup` remains a supported legacy lightweight routing target and is not migrated automatically.

Team codes use a locked singleton `TeamNumberSequence` and have the immutable `TEAM-000001` form. Team lifecycle is DRAFT → ACTIVE → SUSPENDED/ACTIVE → CLOSED. CLOSED is terminal; reopening is deliberately not exposed in Phase 2.2.

## Temporal membership

`TeamMembership` stores immutable participation periods. Role change closes the previous period and creates a new one. Rejoining also creates a new row. Only one open membership per Team/Employee and one open primary LEAD per Team are protected by partial PostgreSQL unique constraints. A PostgreSQL `tstzrange` exclusion constraint backed by `btree_gist` rejects every overlapping historical period for the same Team/Employee, including writes that bypass the service layer. Direct membership is not inherited; descendant membership is included only through an explicit query mode.

## Assignment integration

`AssignmentTarget.TEAM` is separate from `FUNCTIONAL_GROUP`. Strategies are `team_lead`, `team_owner`, `all_active_members`, `role_members` and `explicit_member`. Resolution is read-only, date-aware, excludes inactive employees and rejects suspended, closed or non-assignable teams. Returning multiple employees does not create multiple Work objects or change Work lifecycle.

## API

- `/api/internal/v1/teams/` CRUD (no delete), filters and tree action;
- lifecycle: `activate`, `suspend`, `resume`, `close`, `move`;
- leadership: `assign-owner`, `assign-lead`;
- membership: `members`, `members/history`, nested `change-role`, `end`;
- read-only `resolve` preview;
- `/api/internal/v1/people/employees/{id}/teams/` and `teams/history/`;
- `/api/internal/v1/org-units/tree/`, `move` and `close`.

Service serializers make codes, statuses, versions, hierarchy, leadership, audit fields and lifecycle fields read-only. Hierarchy, leadership and lifecycle changes use dedicated actions with optimistic version checks. Team list/detail/tree, membership and history actions use separate `people.team.*` / `people.team_membership.*` permissions with SQL-filtered object scopes and IDOR-safe querysets. `available_actions` is permission-aware but never replaces server authorization.

## Audit and Outbox

Team, membership and OrgUnit operations publish `people.team.*` / `people.org_unit.*` Audit and Outbox records inside the same transaction. Employee termination ends open memberships and vacates owner/lead without choosing a successor. Reactivation does not restore membership or leadership.

## Migrations

- `organizations.0003`: append-only OrgUnit fields and period constraint;
- `employees.0008`: Team, TeamMembership, sequence and AssignmentTarget Team reference;
- `employees.0009`: hardened exact-reference constraint including explicit Team member semantics.
- `employees.0010`: installs `btree_gist` and adds the no-overlap exclusion constraint for historical Team membership periods.

No FunctionalGroup data is rewritten. Clean install and Phase 2.1 upgrade are mandatory gates.

## Known limitations

- no external/fictitious employee membership;
- no automatic participant inheritance or dynamic SQL teams;
- no automatic successor for terminated leads/owners;
- no mass Task/Request creation from `ALL_ACTIVE_MEMBERS`;
- historical OrgUnit hierarchy is limited to validity/lifecycle fields; parent-edge history is not a separate temporal table.

## Quality gate

Status on 2026-09-02:

- PostgreSQL `17.11`;
- clean migration graph: PASS;
- Phase 2.1 `employees.0007` → current upgrade: PASS;
- migration drift: PASS (`No changes detected`);
- Django system check: PASS;
- Phase 2.2 tests: `23/23 PASS`, including 10 PostgreSQL concurrency scenarios;
- full backend regression: `299/299 PASS`;
- Audit and Outbox rollback: PASS;
- FunctionalGroup resolver regression: PASS.

```bash
docker compose -p ays-connect-pilot -f docker-compose.prod.yml --env-file .env.pilot run --rm -e DJANGO_SECURE_SSL_REDIRECT=0 backend python manage.py test
docker compose ... run --rm backend python manage.py check
docker compose ... run --rm backend python manage.py makemigrations --check --dry-run
```
