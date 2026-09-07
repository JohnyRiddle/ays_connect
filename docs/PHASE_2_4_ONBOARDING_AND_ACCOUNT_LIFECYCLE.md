# Phase 2.4 — Onboarding & Account Lifecycle

## Architecture audit

Phase 2.4 reuses the canonical `accounts.User`, `employees.Employee`, `EmployeeInvitation`, `EmployeeProfile`, Organization/Team, `AssignmentTarget`/`AssignmentResolver`, production `work_tasks.TaskTemplate`/`Task`, Permission, Audit and transactional Outbox domains. No parallel Person, account, task, notification or organization models were introduced. The pre-phase public self-registration request remains generic and never creates an Employee.

The audit found that invitation secrets were already generated with `secrets.token_urlsafe`, stored only as SHA-256 digests, protected by expiry/revoke/one-use checks and accepted under row locks. Phase 2.4 adds explicit lifecycle metadata, first-login progress, rehire support and the versioned onboarding runtime. Login, refresh and JWT authentication now explicitly reject `terminated` employees.

## Account and invitation policy

`Employee.user` is the single nullable OneToOne link. Account state is derived from Employee employment state, `Employee.account_access_state`, `User.is_active`, active invitations and `FirstLoginProgress`: NOT_INVITED, INVITED, REGISTRATION_IN_PROGRESS, ACTIVE, ACCESS_SUSPENDED, ACCESS_BLOCKED, TERMINATED or REACTIVATION_REQUIRED. An account is never created without an existing active Employee.

`EmployeeInvitation` stores only `token_hash` plus a non-secret display prefix. Raw tokens exist only in the service return used by the delivery boundary. Status, intended delivery email, creator, sent/accepted/revoked timestamps, accepted user, revoke reason and optimistic version are retained. Creation serializes on Employee, revokes the previous open invitation, and the database enforces one open invitation and unique digest. Validate/accept use generic failure responses and scoped throttling. Passwords and tokens are excluded from Audit/Outbox payloads.

Termination disables User, blacklists outstanding refresh tokens, revokes invitations, ends assignments/team relationships and cancels active onboarding atomically. Reactivation preserves Employee and `EMP-*`, leaves the User inactive and marks reactivation required. A new invitation may safely reactivate that same User; roles, teams and previous onboarding are not restored.

## First login

`FirstLoginProgress` is a resumable optimistic-locked OneToOne state for profile, timezone and visibility confirmation. Activation creates/reuses `EmployeeProfile` and creates progress. Completion leads to the employee's assigned onboarding. It does not emulate legal acknowledgements or documents.

## Versioned onboarding

`OnboardingTemplate` owns scope and current published version. `OnboardingTemplateVersion` and its ordered `OnboardingTemplateStep` rows are immutable snapshots after publish. Publish validates unique keys/positions, non-empty steps, TASK/LINK requirements and an acyclic dependency graph. Supported step types are PROFILE, ACKNOWLEDGEMENT, MANUAL, TASK, LINK and LEARNING_PLACEHOLDER.

Resolution is SQL-backed and deterministic: explicit template, then position, team, org unit, location, legal entity and global. Equal-priority matches produce a controlled conflict. Scope-specific references are validated at creation.

`OnboardingInstance` retains the selected immutable version and has PENDING/ACTIVE/PAUSED/COMPLETED/CANCELLED/FAILED states. A partial unique constraint permits only one active/pending/paused instance per Employee. `OnboardingStepInstance` snapshots title/description/required flags and tracks responsible resolution, deadline, completion/skip and an optional OneToOne production Task. Progress is calculated only from required steps; dependency release and completion are reconciled transactionally.

Responsible resolution supports self, direct manager, explicit employee, AssignmentTarget/position, team lead/role and org-unit strategies. Inactive or terminated assignees are rejected; unresolved steps remain BLOCKED with a non-sensitive explanation.

TASK steps call the existing `TaskTemplateService`; the locked step plus OneToOne link makes retries idempotent. A PostgreSQL-specific nullable outer-join `FOR UPDATE` failure found by the gate was fixed by locking the step row before loading its optional template relation.

## API and permissions

Internal endpoints:

- `/api/internal/v1/people/invitations/` with create, list, retrieve, resend and revoke;
- `/api/internal/v1/people/onboarding/` with assign, lifecycle, restart, skip, resolve and TASK creation;
- `/api/internal/v1/people/onboarding-templates/` with draft CRUD, publish, archive and resolution preview;
- `/api/internal/v1/people/me/first-login/` and `/people/me/onboarding/` self-service;
- `/api/internal/v1/people/{employee_id}/access/{suspend|restore|block|reactivate}/`;
- `/api/public/v1/auth/invitations/{validate|accept}/` generic public flow.

Permissions use the existing seed catalogue and `PermissionService`: invitation view/create/resend/revoke; onboarding self/view/assign/manage/skip; template view/create/update/publish/archive; and separate access view/suspend/restore/block/reactivate. Employee and onboarding querysets are SQL-scoped; detail endpoints are retrieved from scoped querysets. Server authorization remains authoritative over displayed actions.

## Audit, Outbox, notifications and workers

Invitation, account, template, onboarding, step and task lifecycle mutations emit `people.*` Audit and Outbox records inside their domain transaction. An Audit failure rollback is tested. Domain events are the Notification Core integration boundary; they carry identifiers and state, never credentials or sensitive profile values.

`process_onboarding --batch-size N [--dry-run]` expires invitations, reconciles progress/completion and retries unresolved responsible assignments. Work is bounded and uses `select_for_update(skip_locked=True)` so multiple workers can run safely.

Concurrency uses a global Employee → Onboarding → Step lock order. The PostgreSQL gate covers invitation acceptance/reissue/revoke/termination races, active onboarding assignment, complete/skip, duplicate TASK creation, suspend/restore and termination/completion. A deadlock discovered in termination versus step completion was fixed by taking the Employee lock first. `test_termination_racing_completion_leaves_cancelled_or_completed_history` reproduces that race on PostgreSQL and protects the lock order from regression; `test_task_step_creates_one_production_task` protects the nullable outer-join `FOR UPDATE` correction.

## Frontend and admin

The SPA includes safe activation states, resumable first-login, compact “Мой онбординг”, management onboarding/template tables and invitation status without secret display. Loading, empty and error states and responsive step layout are included. Django Admin provides optimized, mostly immutable history views; tokens and passwords are never exposed and lifecycle mutation remains service-only.

## Migrations and limitations

Append-only migrations are `employees.0013` (domain and invitation lifecycle), `0014` (permissions) and `0015` (account access state). Existing User/Employee/invitation digest data is preserved and deterministically backfilled. Published snapshots are created only by explicit publish operations.

Known limitations: outbound invitation delivery is delegated to the existing event/notification workers; legal document signing, Learning completion integration, SSO/MFA and full BPM editing remain intentionally outside Phase 2.4. Management frontend prioritizes operational lists and service-backed actions over drag-and-drop editing.

## Quality Gate commands

Final local gate results:

- PostgreSQL `17.11` clean migration: PASS;
- upgrade rehearsal `employees.0012 → 0013 → 0014 → 0015`, including preservation of User, Employee, employee number and invitation digest: PASS;
- Phase 2.4 tests: `16/16 PASS`;
- PostgreSQL concurrency suite: `10/10 PASS`;
- full backend regression: `342/342 PASS`, skipped `0`;
- Security/Audit/Outbox leakage and rollback checks: PASS;
- frontend TypeScript/Vite production build: PASS;
- `manage.py check`, migration drift and `git diff --check`: PASS.

Commands:

```bash
python manage.py migrate
python manage.py test employees.test_onboarding employees.test_onboarding_phase24
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py process_onboarding --dry-run
npm run build
git diff --check
```
