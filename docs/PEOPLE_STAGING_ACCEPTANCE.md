# People — LOCAL STAGING ACCEPTANCE

## Проверка интегрированного checkpoint — 27.09.2026

People baseline ниже остаётся проверяемым основанием перехода к Projects. После финального ревью интегрированного People+Projects кода повторно выполнен полный PostgreSQL backend: **444/444 PASS**. Изменение общего Notification Core закрывает выдачу Work reopen/reject уведомлений после утраты текущего SQL-доступа к задаче; соответствующие People/Notification/Projects тесты **65/65 PASS**. Обновлённый live worker использует реальную синтетическую Work-задачу и scoped `task.view`: пять People-причин, по одному logical notification, In-App+Email и пять писем Mailpit — PASS. Утверждённое правило A/B не менялось.

## Финальный итог — 2026-09-15

**LOCAL STAGING ACCEPTANCE: PASS** для утверждённого People scope. Это не production release. Исполняемый код — `main`/HEAD `f13bfce249b0c22311621c577e4337887018f9c3` плюс сохранённые незакоммиченные People-изменения в `C:\Users\riddl\OneDrive\Документы\AYS Connect актуальный`. Отдельный commit не являлся условием gate. Production, реальные аккаунты/credentials, commit/push/deployment не затрагивались.

Утверждённое правило: при Work reopen завершённого A и наличии другого B в `pending/active/paused` B сохраняет статус, A остаётся completed. Атомарно создаются `people.onboarding.reopen_blocked`, Audit и `notification.requested` ответственному за шаг; Notification Core доставляет In-App/Email с настройками каналов. Исходное событие остаётся retryable. Уполномоченный сотрудник явно отменяет B через штатный `people.onboarding.manage` lifecycle command с `version` и причиной, после чего повторная обработка открывает A. Автоматической отмены B и параллельного A нет. Повторы используют детерминированные event IDs и NotificationIntent, без дублей.

| Требование | Финальная проверка/evidence на конечном коде | Результат | Оставшийся blocker |
| --- | --- | --- | --- |
| Конфликт A/B для pending, active, paused | `employees.test_onboarding_events`: три состояния B, неизменность A/B, диагностическое событие и Audit actor | PASS | — |
| Уведомление ответственному и дедупликация | Повтор `process_events`, двойной `ingest_event`, пять People-причин через live Notification worker и Mailpit единственному synthetic recipient | PASS, по одному logical notification и двум каналам | — |
| Ручное разрешение | `OnboardingService.transition(cancel)` с version/reason, повтор source, Audit cancelled/reopened и один receipt; API permission/scope regression в общем suite и gate | PASS | — |
| Конкуренция и rollback | PostgreSQL `TransactionTestCase`: assign B ↔ consume A и два consumer; Audit failure откатывает diagnostic/notification | PASS | — |
| Полный backend и migrations | PostgreSQL 17.11 clean test DB: **414/414**, 97.979s; `manage.py check`, `makemigrations --check --dry-run` | PASS | — |
| Staging API и browser | Новые fixtures `gate26` browser **5/5**; `gate27` browser activation и API **73/73**, blocked 0; role HTTP/service **163/163** для exact95 | PASS | — |
| Frontend build | `frontend_assets` TypeScript/Vite, 1796 modules | PASS | — |
| Business upgrade | Новая `people_business_upgrade_20260915e`: checkpoint accounts0002/work_tasks0003 → latest, 24 объекта, repeat migrate NOOP, policy guard | PASS | — |
| Synthetic backup/restore | Новая `people_business_restore_20260915d`: 179 tables/14333 rows/66 media, все concrete fields/relations/auth_version и SHA256 media совпали, ORM/SQL guard после restore | PASS | — |
| Hygiene | `git diff --check`; известные synthetic secrets/JWT-shaped strings в Audit/Outbox и фактических staging logs | PASS | — |

API на `gate26` был ожидаемо остановлен preflight (`exit 2`) после полного browser rehire: fixture уже не соответствовала условию одной активации. Для окончательного API gate создана новая `gate27` и выполнена отдельная browser activation; **73/73** прошли без маскирования ошибки. Первая попытка role-harness в one-off контейнере также завершилась connection refused, так как harness ожидает localhost работающего backend; окончательный запуск через `exec` работающего backend прошёл **163/163**. Эти попытки не являются security evidence.

Сохранены изолированные staging volumes/DB, новые fixtures `gate26`/`gate27`, upgrade-e/restore-d и synthetic dump в DB-контейнере. Forgotten-password flow остаётся отдельным product gap вне этой acceptance.

## Исторический итог — 2026-09-08

**BLOCKED: требуется бизнес-решение для возврата старого завершённого онбординга, когда уже активен новый.**
Это не production release и не разрешение на восстановление реального аккаунта.
Финальный PostgreSQL regression: **410/410 PASS**, skipped 0, 96.426s (handoff v13), включая запрет legacy DELETE.

Контур: только `ays-people-acceptance`, PostgreSQL **17.11**, internal Docker network,
отдельные DB/Redis/media/private volumes, Email только Mailpit, Telegram выключен.
HEAD `f13bfce249b0c22311621c577e4337887018f9c3`, main; изменения не закоммичены.
Production, pilot, аккаунт Юлии, commit/push и deployment не затрагивались.

## Единая таблица требований

PASS ниже относится к названной проверке, а не ко всем возможным комбинациям системы.
Результат 410/410 не используется как самостоятельное доказательство полной acceptance.

| Требование | Проверка / доказательство | Результат | Оставшийся blocker |
|---|---|---|---|
| 95 / 26 / 30 = 151 | JSON policy + точное сравнение staging registry; отсутствие дублей/неизвестных кодов | PASS | — |
| Consumer-аудит каждого разрешённого кода | OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md: 95 отдельных строк, операции, scope, косвенные эффекты, source/regression references; dynamic permission_domain и registry-only aliases отделены | Source inventory выполнен; не 95 отдельных E2E-тестов | Не выдаёт blanket-гарантии всех комбинаций |
| Синтетическая полная роль | verify_director_full_role.py: точные 95 grants, остальные 56 отсутствуют, без staff/superuser/direct permissions/groups/legacy roles, unusable password | 163/163 PASS на текущем коде; последний synthetic User 238 | — |
| Запрет управления аккаунтами/ролями/оргструктурой | Полная роль: create/patch role, permission grant, self-role assignment, restore account, invitation, position create, terminate, org PATCH, legacy read | Все проверенные операции отклонены | — |
| Политика приёмки до публикации | work_tasks/test_acceptance_policy.py + verify_acceptance_policy_http.py: draft edit, publish/edit race | PASS | — |
| Неизменность после публикации | Sticky flag + migration work_tasks0004 + PG trigger; service, model.save, QuerySet.update, bulk_update, raw SQL, Admin; admin/superuser без обхода | PASS | — |
| No-op, cancel/reopen, атомарный отказ | Та же политика допустима; смена политики с другими полями не сохраняется; force-draft/сброс flag не разблокируют | PASS | — |
| Ответственный и принимающий — разные понятия | test_responsible_reassignment_is_not_a_new_reviewer_api: AUTHOR остаётся автором, RESPONSIBLE следует текущему ответственному; неподходящий actor отклонён | PASS; нового механизма reviewer нет | — |
| Scope: view не расширяет write | test_template_scope.py; test_acceptance_gaps.py: Work template/recurrence original+candidate scope, Onboarding create/move/explicit template, rollback | PASS | — |
| Пустой контекст не означает общую область | access_control/test_null_scope_consumers.py: Task/Request/Performance NULL org/legal context не открывает несвязанные записи; положительный контекст работает | PASS | — |
| A — приглашение/регистрация | test_onboarding.py: hash-only, expiry/revoke/used/invalid/inactive, reissue, one-time activation, validation rollback; phase24 concurrency accept/revoke/terminate; API gate25 + browser gate24 | PASS для перечисленных контрактов | — |
| B — профиль, privacy, avatar | API gate25: self allowlist, valid/invalid/oversized avatar, protected download, HR/manager/colleague/outside personas; profile tests + browser desktop/mobile/refresh | PASS | — |
| C — кадровые change requests | test_profile_phase23.py: lifecycle, self-approval denial, stale apply, cancel, approve/reject/cancel races; gate25 scoped review + sensitive, IDOR, idempotent apply | PASS | — |
| Раскрытие reviewer-у значений только с sensitive | test_acceptance_gaps.py + gate25: review без sensitive маскирует значения; оба scoped permissions раскрывают; out-of-scope отказ | PASS | — |
| D — onboarding snapshots/dependencies | phase24 tests: immutable published version/step, cycles, dependency completion, version conflict, assignment/Task creation races, Audit rollback; explicit-template scope regression | PASS | — |
| E — Work → People event | test_onboarding_events.py: exact linked Task/version, repeat/delayed events, progress/history/actor, no duplicate Task, cancelled/terminated exclusions, Audit rollback | PASS обычного возврата | Конфликт с более новым активным onboarding — см. ниже |
| F — уведомления | Live verify_people_notification_worker.py: 4 причины, по одной logical notification и In-App/Email delivery, 4 различных письма единственному synthetic recipient в Mailpit | PASS | — |
| Повтор/quiet hours/preferences/recipients | Multichannel tests для 4 People-причин; overdue interval/dedup; два concurrent overdue workers; inactive/missing recipient diagnostics; suppressed delivery без attempt | PASS | — |
| Вложения и скачивание | Полная роль: upload через доменный сервис, точные bytes HTTP download, чужой actor/неверный parent/deleted download denied, delete без conditional permission denied, Audit actor | PASS | Scanner hook по умолчанию no-op; это не антивирусная проверка |
| G — suspend/restore/JWT/session | verify_auth_http.py и accounts/test_revocation.py: old access+refresh не оживают, новый вход работает; Django sessions/legacy JWT/stale save/Audit rollback | PASS | — |
| Альтернативные Admin/write paths | User Admin lifecycle fields read-only; Employee Admin lifecycle/user read-only; generic Employee PATCH отвергает lifecycle fields атомарно; legacy DELETE запрещён; legacy block/unblock используют lifecycle service | PASS | Прямой административный SQL к User не является проверенным lifecycle API |
| H — termination | gate25 и phase24 races: access/roles/teams закрываются; Employee/User/profile/Task/history сохранены; повтор безопасен | PASS | — |
| I — browser rehire | gate24: новая synthetic credential через activation UI, сохранение identity, старый пароль/access/refresh отвергнуты, прежние роли не возвращены, UI login новым паролем | 5/5 browser suite PASS | — |
| Clean migrations | Полный backend suite создаёт чистую PostgreSQL test DB и применяет все миграции | PASS | — |
| Upgrade после DB guard | verify_business_upgrade.py, новая БД people_business_upgrade_20260908d: accounts0002/work_tasks0003 → latest, 24 связанных объекта/все старые поля, draft/non-draft/history backfill, policy refusal, повтор NOOP | PASS | — |
| Backup/restore DB guard | Новая people_business_restore_20260908c: 179 tables / 11730 rows / 55 media files, все concrete fields/relations/auth_version и SHA256 media совпали; ORM и raw SQL guard после restore, повторный fingerprint неизменен | PASS | Источник не перезаписывался; это synthetic snapshot, не production backup |
| Финальные проверки | 410-test PG suite, API73, role163, browser5, frontend production build; check/migration drift/diff/secret scan | PASS по выполненным проверкам | Бизнес-конфликт выше не закрывается зелёным suite |

## Повторная проверка передачи — 08.09.2026, handoff v13

Фактический рабочий каталог: `C:\Users\riddl\OneDrive\Документы\AYS Connect актуальный`.
Подключённый `AYS Connect` содержит другой HEAD `e03731c` и не изменялся.
Миграционные leaves подтверждены через MigrationLoader: accounts0003, employees0015,
work_tasks0004; остальные leaf nodes не изменены. Backend код в этой проверке не менялся.

- Full backend: 410/410, skipped 0, 96.426s; concurrency, JWT/session, Admin,
  immutable policy, privacy и Audit/Outbox rollback входят в этот suite.
- API gate25: 73/73 после browser activation; проверен также отказ preflight с exit 2.
  Скрипт теперь возвращает exit 1 при любом FAIL/BLOCKED и не начинает lifecycle
  мутации без активированной fixture. Ранний gate20 был ошибкой порядка запуска:
  7 PASS / 2 FAIL / 7 BLOCKED; он не используется как security evidence.
- Browser gate24: 5/5 на финальном тестовом коде, включая desktop/mobile и rehire.
  Gate21: 4/5 (ожидание worker исчерпало 5 секунд); gate23: 4/5 (UI login после
  rehire не учитывал throttle). Ожидание reconciliation теперь 15 секунд;
  UI учитывает валидный Retry-After однократно, затем всё равно требует HTTP 200.
  Проверки статусов и отзыва credentials не ослаблены. Fonts interception отсутствует.
- Полная роль: 163/163, synthetic User 238. Добавлены проверка effective 95 в own
  context, единственной active role, всех 56 excluded/conditional, точные коды отказов
  и сравнение RBAC/Employee/OrgUnit данных до и после отказа. AccountAccessView скрывает
  объект через scoped queryset: ожидается 404/request_failed; attachments ожидают
  400/task_permission_denied либо 400/request_permission_denied, а не произвольный 400.
  В обоих подразделениях также прошли create/edit/publish/start/complete/reject/accept/reopen,
  внутренний комментарий, Audit actor, template create/use, recurrence create/pause,
  onboarding template/publish/assign/start/skip и management summary. SLA calendar/interval/
  publish, policy create/publish и scoped assignment rule прошли без изменения RBAC.
  Это набор конкретных сценариев; не 163 разных permission consumers.
- Upgrade-d: 24 связанных объекта, все прежние поля, policy backfill, отказ изменения,
  повтор migrate NOOP. Restore-c: 179 таблиц / 11730 строк / 55 media, поля/связи/hash
  совпали, ORM и SQL guard работают. Исходная staging БД не перезаписывалась.
- `verify_restored_revocation.py`: токены выданы синтетическому пользователю до
  suspend/restore и сохранены только в private volume. После восстановления проверены
  валидность подписи/срока старого access, отказ по отзыву, отказ старого refresh,
  изменение session hash и приём новой генерации. Проверочные записи откатились.
- После backup staging backend/оба worker запущены снова; четыре причины уведомлений
  повторно доставлены ровно по двум каналам, четыре письма только synthetic recipient
  в Mailpit. Sensitive scan Audit/Outbox и фактических логов PASS.
- Изменены только acceptance harness, воспроизводимость и документация. Бизнес-решение
  по competing onboarding не принято; runtime policy сохранена, sign-off BLOCKED.

Сохранены новые synthetic fixtures gate20–gate25, User 238 и isolated upgrade-d/restore-c,
контейнеры handoff-regression-v13/build-v3/restore-c/restored-auth-c/browser-gate24,
private credential fixture и dump-c. Секреты и runtime artifacts не добавлены в Git.

## Исторический конфликт, разрешённый правилом 15.09.2026

Если completed onboarding A возвращается из-за Work-события, но onboarding B уже
pending/active/paused, запрещено создать второй active instance существующим DB constraint.
Текущее безопасное поведение сохраняет обе записи и новый onboarding, создаёт
`people.onboarding.reopen_blocked`, оставляет исходное событие retryable.
Не производится автоматическая отмена B, перенос шагов или переписывание истории.
Регрессионный тест подтверждает сохранность; это не утверждённое разрешение бизнес-конфликта.
Нужно решить, остаётся ли B активным с ручным разрешением конфликта либо разрешается
явный переход, освобождающий место для A. Без этого соответствующий acceptance-case BLOCKED.

## Границы доказательств и поведения

- Для каждой из 95 permissions описан фактический consumer или его отсутствие.
  Registry-only коды не считаются реализацией отсутствующей функции. OWN endpoints
  используют текущую identity; добавление кода не открывает чужой профиль.
- 163 проверки полной роли — сквозной набор positives/negatives, а не 95 независимых
  сценариев записи. В proof используются также source tracing и domain regression.
- `task.reassign` меняет responsible/executor. Отдельного поля/API назначения reviewer нет.
  Reviewer вычисляется из AUTHOR/RESPONSIBLE. Общего запрета на совмещение executor и
  responsible в существующей модели нет; новый запрет/механизм в этом задании не вводился.
- Указание scanner означает вызов extension hook; default AttachmentScanner.scan — no-op.
  Проверены ограничения типа/размера/имени и ACL, не поиск вредоносного содержимого.
- `PEOPLE_OVERDUE_REPEAT_HOURS` теперь читается из environment, default 24, minimum 1.
  Получатели: ответственный + assigned_by coordinator, дедупликация по Employee.
- Email отправлялся только в Mailpit. Google Fonts не перехватываются: внешний import удалён,
  браузерный тест проверяет отсутствие запросов к Google. Только error-UI case вводит HTTP 503.
- Browser retry уважает реальный login throttle 5/min и Retry-After; security assertions не ослаблены.
- Secrets scan охватывает известные synthetic passwords, staging signing key, JWT-shaped strings
  в Audit/Outbox/логах. Это не доказательство отсутствия всех видов PII.
- Синтетические fixtures создаются под уникальными run IDs; реальные записи не переиспользуются.
  Проверки deleted downloads меняют только metadata собственных тестовых вложений;
  физические файлы сохранены. Диагностические контейнеры/БД и dumps оставлены.

## Артефакты и воспроизводимость

- Backend: `ays-people-handoff-regression-v13` (410/410, skipped 0, 91.769s).
- Browser: `ays-people-browser-gate24` — 5/5.
- API: `verify_people_api.py gate25` — 73/73.
- Role: `verify_director_full_role.py` — 163/163; не использовать старый 8-permission smoke как полный gate.
- Frontend: `ays-people-handoff-build-v3` — TypeScript/Vite build PASS, 1796 modules.
- Dump: staging DB container `/tmp/people_business_20260908c.dump`.
- Restore media: isolated private volume `business-restore-20260908c`.
- До work_tasks0004 исторические 391/397 и restore-a не являются текущим доказательством DB guard.
- Локальные секреты, базы, media и runtime artifacts не добавлялись в Git.

## Отдельный product gap

Forgotten-password flow не реализован и не заменяется административным restore.
Это отдельный scope: token lifecycle, anti-enumeration, delivery, throttling/revocation.
В этом задании не добавлялся и не обходился выдачей реальных паролей через чат.
