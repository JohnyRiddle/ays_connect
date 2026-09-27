# Operations Director — Access Matrix

**APPROVED POLICY / SYNTHETIC ROLE CHECKED — NOT APPLIED TO PRODUCTION**

Источник: пользовательское ТЗ `389f3fe6-1a0d-404c-bb50-b018aea7ad37`, 2026-09-08.
Версионируемая политика: `backend/access_control/operations_director_policy.json`.
Импорт loader не создаёт роли и ничего не назначает. Production seeds отсутствуют.

## Точные категории

Программная сверка фактического staging-реестра: **151 код = 95 Да + 26 Нет + 30 Условно**.
Актуальное ТЗ подтверждает 95/26/30; исторические подписи 92/33 заменены явными списками.
Дубликатов, отсутствующих и новых неизвестных кодов нет.
Новые permissions не наследуются автоматически. Всё вне allowlist запрещено к назначению.
Бизнес scope GLOBAL; self permissions OWN и ограничение текущим User на endpoint.
`is_staff=False`, `is_superuser=False`; без direct user_permissions/groups/legacy roles.

Роль с точными 95 permissions проверена только на отдельных синтетических staging identities:
163/163 positive/negative проверок, включая запрещённые административные операции и download ACL.
Операции, scope, косвенные эффекты и source/regression evidence каждого кода:
`OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md`. Это не утверждение о 95 независимых E2E-сценариях.
Предыдущая отдельная синтетическая роль с 8 read permissions остаётся историческим
частичным тестом (27/27), не доказательством текущей матрицы.
Реальный User ID 2 не подключался и не изменялся.

## Подтверждённые технические ограничения

- **Исторический BLOCKED: task.edit — исправлен 08.09.2026.** Ранее TaskPatchSerializer и TaskService.update позволяли сменить
  acceptance_policy с author/responsible на none у IN_PROGRESS Task. Диагностический
  `work_tasks.test_access_matrix_audit` воспроизвёл обход без staff/superuser.
  По согласованию: политика меняется лишь в draft до первой публикации; sticky marker,
  domain check и DB trigger закрывают service/ORM/bulk/Admin без superuser bypass.
  Диагностический тест заменён regression запрета; 7 целевых проверок и живой HTTP PASS.
  Полный suite 397/397 PASS. Это снимает данный блокер, но не заменяет полный consumer audit.

- `task.accept` / `task.reject` проверяются вместе с фактическим author/responsible
  в `TaskService._validate_reviewer`: GLOBAL не отменяет обязательную политику приёмки.
  При несовпадении actor — `task_review_not_allowed`. Подмена actor запрещена.
- `people.onboarding.manage` вызывает onboarding lifecycle/TaskTemplateService,
  но не выдаёт User access или роли. Task creation отдельно требует template.use/task.create.
- Onboarding mutations теперь выбирают scope именно manage/step_skip, а не view.
  Temporal grants/null context в видимости onboarding templates исправлены с regression.
  Create/explicit-template и mixed Work-template scope пути закрыты отдельными regression tests.
- Task template и SLA policy APIs изменяют бизнес-модели; account/role endpoints используют
  отдельные запрещённые permissions. Source inventory и runtime evidence разделены в отчёте.
- Invitation serializer содержит метаданные, не token_hash/activation token/password.
- HR review/apply и sensitive остаются Условно, не выдаются. Для раскрытия reviewer-у значений
  кадрового запроса нужны одновременно review и scoped sensitive (согласовано отдельно).
- `employee.manage` включает назначение EmployeeRole и Position writes; запрещён.
  `people.employee.manage` включает termination/reactivation User; запрещён.
  `request_type.manage` включает access rules; запрещён.
- Forgotten-password endpoint отсутствует; не создавать его и не выдавать пароль через чат.

## Полная матрица

Consumer-ссылки ниже — исторические исходные точки аудита, а не blanket подтверждение всех путей.
Актуальные операции каждого кода приведены в OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md;
итоговые проверки и единственный бизнес-конфликт — в PEOPLE_STAGING_ACCEPTANCE.md.

| Permission | Решение | Целевой scope | Consumer / точка проверки |
|---|---|---|---|
| `people.employee.view` | Да | GLOBAL | Directory API: list/detail, account metadata and active role names; no account writes; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.directory.view` | Да | GLOBAL | Active directory/detail/avatar through visible_employees and privacy masking; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.directory.view_inactive` | Да | GLOBAL | Registry-only: DirectoryViewSet still filters is_active=True; this code does not unlock inactive directory; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.profile.view_self` | Да | OWN | Registry declaration; MeView authorizes current authenticated active Employee, not this code; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.profile.update_self` | Да | OWN | Registry declaration; own profile/visibility/avatar APIs use actor identity and field allowlist; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.invitation.view` | Да | GLOBAL | Invitation list/detail metadata; serializer excludes token/hash/password; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding.view_self` | Да | OWN | Own onboarding list/detail/start and first-login flags; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding.step_complete_self` | Да | OWN | Own step start/complete; dependencies and linked Work final status still required; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding.view` | Да | GLOBAL | Scoped instance list/detail, steps and resolver preview employee selection; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding.assign` | Да | GLOBAL | Assign published template to scoped Employee; creates instance/step snapshots, not User/roles; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding.manage` | Да | GLOBAL | Start/pause/resume/cancel/restart/resolve/create-task; Work creation additionally checks task_template.use/task.create; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding.step_skip` | Да | GLOBAL | Skip scoped step with reason; affects progress, not account/role access; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding_template.view` | Да | GLOBAL | List/detail/preview; shared global templates readable to scoped actors; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding_template.create` | Да | GLOBAL | Create draft; matching scope reference required; denied candidate and Audit/Outbox roll back; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding_template.update` | Да | GLOBAL | Edit current draft/version; scoped object and resulting scope checked atomically; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding_template.publish` | Да | GLOBAL | Publish immutable version/step snapshots; affects future onboarding, no access grants; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.onboarding_template.archive` | Да | GLOBAL | Archive template; existing snapshots preserved; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.account_access.view` | Да | GLOBAL | Registry-only; account state is returned by employee directory consumer instead; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.change_request.create_self` | Да | OWN | Registry declaration; own submit/cancel governed by current Employee and service field allowlist; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.change_request.view_self` | Да | OWN | Registry declaration; own change-request queryset filters current Employee; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.assignment.view` | Да | GLOBAL | Employee assignment history read; POST requires excluded people.assignment.manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.organization.view` | Да | GLOBAL | Registry-only alias; organization reads use organization.view or own OrganizationView; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.manager.view` | Да | GLOBAL | Manager/direct reports/management chain, filtered visible Employee IDs; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.group.view` | Да | GLOBAL | Registry-only alias; group reads use functional_group.view; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.responsibility.view` | Да | GLOBAL | Registry-only; no permission-gated consumer discovered; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.account.view` | Да | GLOBAL | Registry-only alias; directory exposes account metadata, no credentials; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.performance.view` | Да | GLOBAL | Registry-only alias; analytics consumers use performance.view/view_management; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.team.view` | Да | GLOBAL | Team list/detail and scoped visible_teams; writes require separate team permissions; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.team_membership.view` | Да | GLOBAL | Current team memberships, read-only; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `people.team_membership.view_history` | Да | GLOBAL | Historical team memberships, read-only; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `organization.view` | Да | GLOBAL | Legal entity/org unit/tree reads through InternalAPIPermission; mutations require organization.manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `location.view` | Да | GLOBAL | Location reads through InternalAPIPermission; mutations require location.manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `functional_group.view` | Да | GLOBAL | FunctionalGroup reads through dynamic permission_domain; membership writes require manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.create` | Да | GLOBAL | Create canonical draft, number/history/Audit/Outbox; does not publish; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.view` | Да | GLOBAL | Task selectors/list/detail/activity and attachment download; deleted files filtered; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.edit` | Да | GLOBAL | Edit allowed fields/move parent; published acceptance policy frozen in service and DB; no author/User updates; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.assign` | Да | GLOBAL | Publish draft and snapshot resolved responsible/executor targets; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.reassign` | Да | GLOBAL | Change responsible/executor with history/reason; does not change acceptance policy; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.change_deadline` | Да | GLOBAL | Deadline change with reason/version and immutable initial deadline history; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.start` | Да | GLOBAL | Work start through state machine/version lock; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.pause` | Да | GLOBAL | Wait/resume and waiting-period history; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.complete` | Да | GLOBAL | Complete or submit to review according to acceptance/completion policy and checklist requirements; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.accept` | Да | GLOBAL | Accept only actual policy reviewer; global/admin does not override reviewer identity; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.reject` | Да | GLOBAL | Reviewer rejection with reason; creates Work event consumed by onboarding; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.cancel` | Да | GLOBAL | Cancel with reason/state checks and waiting-period closure; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.reopen` | Да | GLOBAL | Reopen completed Work, emit versioned event; does not clear policy lock; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.comment` | Да | GLOBAL | Create/edit/delete own public comments; other authors require conditional moderation; other-employee mentions require conditional employee.view; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.comment_internal` | Да | GLOBAL | Internal comment read/create and visibility changes; not moderation of other authors; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.attachment_add` | Да | GLOBAL | Validated/scanned upload; DB/Audit failure removes newly stored file; not deletion permission; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.watch` | Да | GLOBAL | Add/remove self watcher; other Employee requires conditional watcher_manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.checklist_manage` | Да | GLOBAL | Manage Task checklist/items, no template-role/account access; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task.checklist_complete` | Да | GLOBAL | Complete checklist item under Work collaboration policy; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `checklist_template.view` | Да | GLOBAL | Read checklist templates/items; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `checklist_template.manage` | Да | GLOBAL | Create/update checklist templates/items; shared business content; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task_template.view` | Да | GLOBAL | Read scoped Work templates; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task_template.manage` | Да | GLOBAL | Create/edit/deactivate template and stop associated recurrences; original and candidate scope checked in services; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task_template.use` | Да | GLOBAL | Instantiate active template; additionally requires task.create and task.assign when publishing; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task_recurrence.view` | Да | GLOBAL | Read recurrence rules/occurrences through template scope; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task_recurrence.manage` | Да | GLOBAL | Create/update/pause/resume/skip; template scope and retarget checked; schedules future Work; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `task_recurrence.run` | Да | GLOBAL | Retry FAILED occurrence; target scope checked; generator creates Work under configured author; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `service_catalog.view` | Да | GLOBAL | Read category/service business catalog endpoints; available request-type catalog additionally uses request.create; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request_type.view` | Да | GLOBAL | Read type/schema fields/options/access-rule metadata; rule mutations require excluded request_type.manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.create` | Да | GLOBAL | Create validated typed Request; access rules/routing/SLA initialization apply; no User grants; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.create_for_others` | Да | GLOBAL | Additional guard for another requester; still request.create and request-type access policy; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.view` | Да | GLOBAL | Scoped Request list/detail/activity/files; internal content has additional visibility guard; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.edit` | Да | GLOBAL | Edit allowed request fields with optimistic lock and state restrictions; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.assign` | Да | GLOBAL | Resolve target and assign Request with history; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.reassign` | Да | GLOBAL | Reassign current assignee with reason/version; no EmployeeRole writes; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.start` | Да | GLOBAL | Start/resume Request, close wait and drive SLA lifecycle; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.wait` | Да | GLOBAL | Requester/external wait with required comment, SLA pause semantics; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.resolve` | Да | GLOBAL | Resolve with result through state machine and SLA lifecycle; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.close` | Да | GLOBAL | Close resolved Request through lifecycle, no deletion; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.reopen` | Да | GLOBAL | Reopen Request, retain history and drive SLA lifecycle; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.cancel` | Да | GLOBAL | Cancel Request with reason/lifecycle; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.task_create` | Да | GLOBAL | Atomic canonical Work creation/link; linked object and Audit/Outbox roll back together; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request_routing.view` | Да | GLOBAL | Read routing-rule configuration; mutation requires separate request_type.manage/request_routing.manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.comment` | Да | GLOBAL | Public comment create/edit/delete own; other-author moderation separate; mention recipient must see Request; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.comment_internal` | Да | GLOBAL | Internal note read/create; mentioned recipient must also see internal content; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.attachment_add` | Да | GLOBAL | Validated/scanned upload; final-state restrictions and storage rollback; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.attachment_internal` | Да | GLOBAL | Internal upload/read in addition to relevant parent permission; deletion remains separate; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `request.watch` | Да | GLOBAL | Self watch/unwatch; other watcher requires conditional watcher_manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla_calendar.view` | Да | GLOBAL | Read calendar, versions, intervals and exceptions; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla_calendar.manage` | Да | GLOBAL | Edit/deactivate/publish business calendars and nested intervals/exceptions; affects future SLA calculations; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla_policy.view` | Да | GLOBAL | Read policies/versions and calculation previews; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla_policy.manage` | Да | GLOBAL | Edit/deactivate draft SLA policy; no direct runtime-instance write; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla_policy.publish` | Да | GLOBAL | Publish immutable SLA policy version; endpoint also requires manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla_assignment_rule.view` | Да | GLOBAL | Read policy selection rules; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla_assignment_rule.manage` | Да | GLOBAL | Edit/deactivate SLA selection rules; changes future policy resolution, not RBAC; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla.instance.view` | Да | GLOBAL | Read Request SLA instances/history; runtime management permission remains conditional; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla.escalation_policy.view` | Да | GLOBAL | Read escalation policies/rules/actions/version snapshots; writes require conditional manage/publish; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla.escalation_binding.view` | Да | GLOBAL | Read escalation binding configuration; no binding mutation; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `sla.escalation_instance.view` | Да | GLOBAL | Read runtime escalation history; no retry/cancel/manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `performance.view` | Да | GLOBAL | Read scoped employee aggregates/drilldown; lazy aggregate calculation is an indirect DB write, not access mutation; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `performance.view_management` | Да | GLOBAL | Management analytics over visible Employee scope; shares visibility union with performance.view; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `notification.template.view` | Да | GLOBAL | Read notification templates; POST preview and mutations require conditional manage; proof: OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md |
| `employee.manage` | Нет | не назначать | EmployeeViewSet mutations incl roles, assignments, terminate; PositionViewSet writes |
| `people.invitation.manage` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_api.py:208`, `backend/employees/onboarding_api.py:215` |
| `people.registration.manage` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_api.py:252`, `backend/employees/onboarding_api.py:255`, `backend/employees/onboarding_api.py:260` |
| `people.account.manage` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_api.py:223`, `backend/employees/onboarding_api.py:230` |
| `people.employee.manage` | Нет | не назначать | EmployeeDirectoryViewSet create/update/terminate/reactivate |
| `people.invitation.create` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_phase24_api.py:93`, `backend/employees/onboarding_phase24_api.py:94` |
| `people.invitation.resend` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_phase24_api.py:103` |
| `people.invitation.revoke` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_phase24_api.py:112` |
| `people.account_access.suspend` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_phase24_api.py:301` |
| `people.account_access.restore` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_phase24_api.py:309` |
| `people.account_access.block` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_phase24_api.py:310` |
| `people.account_access.reactivate` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_phase24_api.py:311` |
| `people.assignment.manage` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_api.py:149` |
| `people.organization.manage` | Нет | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `people.manager.manage` | Нет | не назначать | Runtime consumer: `backend/employees/onboarding_api.py:191`, `backend/employees/onboarding_api.py:192` |
| `people.group.manage` | Нет | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `people.team.manage` | Нет | не назначать | Runtime consumer: `backend/employees/teams_api.py:41`, `backend/employees/teams_api.py:93` |
| `people.team_membership.manage` | Нет | не назначать | Runtime consumer: `backend/employees/teams_api.py:90`, `backend/employees/teams_api.py:92` |
| `organization.manage` | Нет | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `location.manage` | Нет | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `functional_group.manage` | Нет | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `role.view` | Нет | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `role.manage` | Нет | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `request_type.manage` | Нет | не назначать | RequestTypeViewSet PATCH, fields/options and access-rules POST |
| `system.status.view` | Нет | не назначать | Runtime consumer: `backend/operations/views.py:23` |
| `notification.delivery.manage` | Нет | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `employee.view` | Условно — не выдавать | не назначать | Runtime consumer: `backend/work_tasks/collaboration.py:38` |
| `people.directory.view_extended` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `people.profile.manage` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `people.profile.view_sensitive` | Условно — не выдавать | не назначать | `employees/profile_api.py:ChangeRequestSerializer._safe`, `employees/profile_services.py:can_see`; review values need review AND scoped sensitive |
| `people.change_request.review` | Условно — не выдавать | не назначать | Runtime consumer: `backend/employees/profile_api.py:113`, `backend/employees/profile_api.py:118` |
| `people.change_request.apply` | Условно — не выдавать | не назначать | Runtime consumer: `backend/employees/profile_api.py:113`, `backend/employees/profile_api.py:118` |
| `people.change_request.manage` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `people.responsibility.manage` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `people.team.create` | Условно — не выдавать | не назначать | Runtime consumer: `backend/employees/teams_api.py:87`, `backend/employees/teams_api.py:125` |
| `people.team.update` | Условно — не выдавать | не назначать | Runtime consumer: `backend/employees/teams_api.py:43`, `backend/employees/teams_api.py:88` |
| `people.team.close` | Условно — не выдавать | не назначать | Runtime consumer: `backend/employees/teams_api.py:41`, `backend/employees/teams_api.py:89` |
| `audit.view` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `task.admin` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `task.comment_moderate` | Условно — не выдавать | не назначать | Runtime consumer: `backend/work_tasks/collaboration.py:62`, `backend/work_tasks/collaboration.py:90` |
| `task.attachment_delete` | Условно — не выдавать | не назначать | Runtime consumer: `backend/work_tasks/collaboration.py:126` |
| `task.watcher_manage` | Условно — не выдавать | не назначать | Runtime consumer: `backend/work_tasks/collaboration.py:136`, `backend/work_tasks/collaboration.py:153` |
| `service_catalog.manage` | Условно — не выдавать | не назначать | Runtime consumer: `backend/service_requests/views.py:28`, `backend/service_requests/views.py:33`, `backend/service_requests/services.py:45` |
| `request_type.publish` | Условно — не выдавать | не назначать | Runtime consumer: `backend/service_requests/views.py:32`, `backend/service_requests/services.py:99` |
| `request.admin` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `request_routing.manage` | Условно — не выдавать | не назначать | Runtime consumer: `backend/service_requests/views.py:107`, `backend/service_requests/views.py:112` |
| `request.comment_moderate` | Условно — не выдавать | не назначать | Runtime consumer: `backend/service_requests/collaboration.py:58`, `backend/service_requests/collaboration.py:74` |
| `request.attachment_delete` | Условно — не выдавать | не назначать | Runtime consumer: `backend/service_requests/collaboration.py:96` |
| `request.watcher_manage` | Условно — не выдавать | не назначать | Runtime consumer: `backend/service_requests/serializers.py:64`, `backend/service_requests/collaboration.py:103`, `backend/service_requests/collaboration.py:115` |
| `sla.instance.manage` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `sla.escalation_policy.manage` | Условно — не выдавать | не назначать | Runtime consumer: `backend/sla/views.py:109` |
| `sla.escalation_policy.publish` | Условно — не выдавать | не назначать | Runtime consumer: `backend/sla/views.py:113` |
| `sla.escalation_binding.manage` | Условно — не выдавать | не назначать | Runtime consumer: `backend/sla/views.py:140` |
| `sla.escalation_instance.manage` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `notification.template.manage` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |
| `notification.delivery.view` | Условно — не выдавать | не назначать | Прямого literal-consumer нет в runtime-поиске; generic dispatch проверять отдельно, не выдавать |

## Проверки новой матрицы

- Registry/категории/counts: PASS.
- Новое синтетическое назначение 95 permissions: PASS; User 238, handoff recheck.
- Полная роль: 163/163 конкретных HTTP/service/effective checks; границы в PEOPLE_STAGING_ACCEPTANCE.md.
- Consumer inventory: 95 строк; indirect/generic/legacy/serializer/download evidence приведены отдельно. Это не 95 независимых E2E.
- Исторический read-only staging subset: 8 permissions, 27 проверок; не текущий gate.
- Production applied: **NO**.
