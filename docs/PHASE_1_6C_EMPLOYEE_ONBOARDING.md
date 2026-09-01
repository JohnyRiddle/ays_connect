# Phase 1.6C — Employee Onboarding & Directory

`Employee` remains the organizational person and `User` the authentication identity. The canonical optional one-to-one link is `Employee.user`; activation never grants roles. Access still requires active User + active Employee and `EmployeeRole`/`PermissionService` scope authorization.

The directory routes are `/people/employees`, `/people/employees/:id` and `/people/registrations`. Search, filters, ordering, pagination and visibility are server-side. The permissions are `people.employee.view`, `people.invitation.manage`, `people.registration.manage` and `people.account.manage`.

`EmployeeInvitation` stores only SHA-256 of a 256-bit random token. Raw activation URL exists only in the issue response. Default TTL is 48 hours (`EMPLOYEE_INVITATION_TTL_HOURS`). Tokens are one-time and revocable; reissue revokes the previous open invitation under an Employee row lock plus a partial unique constraint. Activation atomically validates the password with Django, creates User, links Employee, consumes the invitation and writes Audit/Outbox.

Controlled registration accepts only full name and work email at `POST /api/public/v1/register/`; no password is retained, Employee is never auto-created or name-matched, duplicate pending requests are bounded, and the response is generic. Approval selects an existing Employee and creates a normal invitation. Activation is exposed as `GET|POST /api/public/v1/activate/:token/`. Both public flows are throttled.

Raw tokens, passwords, activation URLs and JWTs are not stored in domain/Audit/Outbox records. Invalid, expired, used and revoked links share public error semantics. Account blocking uses canonical `User.is_active`, independently of Employee deactivation. Records are retained as minimal audit/reconciliation history.

## Gate evidence — 01.09.2026

- PostgreSQL 17.11 clean migration PASS; two restores of checkpoint backup `20260901T033759Z` preserved Employee/Task/Request and applied only `employees.0006`.
- Backend PostgreSQL `264/264 PASS`; onboarding/concurrency `10/10 PASS`.
- 1,000 Employee isolated scale smoke: bounded result, 6 SQL queries, search plan 0.412 ms; no list N+1.
- Production frontend build PASS; Playwright `15/15 PASS`, including invitation activation/login/Work/block, registration approval/activation and 390 px responsive People routes. Direct-route SPA fallback covers all People and existing Work routes.
- Pilot upgraded without reset; invite/activate/login, registration/approve/activate, scoped Work and block/unblock PASS.
- Backup `20260901T083654Z` checksums PASS. Isolated DB/media restore preserved 10 Employees, 11 invitation history records, 4 registrations, roles and Work objects; used/revoked state remained immutable.
- `pip-audit` and production `npm audit`: no known vulnerabilities.

Status: **PHASE 1.6C COMPLETE; PHASE 1.6 LOCAL GATES PASS.** Work Core v1.0 remains NOT YET pending Phase 1.6B.
