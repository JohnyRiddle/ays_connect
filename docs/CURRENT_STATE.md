# Текущее состояние AYS Connect

## Projects UX — локальный staging candidate, 02.10.2026

На базе актуального `origin/main` (`d2f91d0`) в отдельной ветке `codex/projects-ux`
перекомпонована страница проекта: компактная шапка, задачи по умолчанию, URL-состояние
фильтров/страницы/вкладок/представлений, server-side фильтрация до пагинации с totals,
этапные группы, split-create, task menus, lazy-loading и адаптивный mobile UI. Боковая
навигация сгруппирована; профиль разделён на read-only `/people/me` и self-service
`/people/me/edit`, доступные через клавиатурное меню аккаунта со штатным logout.

Финальные проверки: frontend production build PASS, Projects + TaskTemplate PostgreSQL **34/34**,
Projects browser acceptance **2/2**, расширенный UX/account browser gate **2/2**. Положительный
browser-сценарий «Из шаблона» использует `task_template.view/use` scope `own` и проверяет
одну Work Task, этап, параметры, приёмку и idempotent repeat без дубля. Desktop и mobile
evidence получены на синтетическом проекте «Запуск сезона». Подробности и
воспроизводимые команды: [PROJECTS_UX.md](PROJECTS_UX.md). Commit/push/deployment и
production-операции не выполнялись.

## Integrated People + Projects + iiko + Cards candidate — 27.09.2026

На базе `8d9fc81` в изолированном checkout `AYS Connect integrated release`, ветка
`codex/integrated-release`, объединены принятые People/Projects и production-exact iiko,
Cards/seasons и backup hotfix. Production inventory выполнен read-only; секреты, БД,
media и data logs не копировались. Полный новый gate: backend **546/546**, iiko
**102/102**, People API/browser **73/73 + 5/5**, Projects **37/37 + 2/2**, Cards/iiko
browser **1/1**, frontend build, production-cutoff upgrade и synthetic backup/restore —
PASS. Staging Compose исправлен: workers ждут окончания миграций. Commit/push не
выполнялись. Deployment заблокирован до immutable checkpoint и проверенного off-host
restore point. Инвентаризация, SHA-256, gate и runbook:
[INTEGRATED_RELEASE_2026_09_27.md](INTEGRATED_RELEASE_2026_09_27.md).

## Финальное ревью People + Projects — 27.09.2026

Полный локальный diff от `f13bfce`, включая новые файлы, проверен в `AYS Connect актуальный` / `codex/projects`. Исправлены lifecycle-валидация ответственных и дат при создании Project stage/milestone, строгий контракт write payload и отзыв Work-уведомлений при потере SQL-доступа к задаче. Финальный PostgreSQL backend **444/444**, Projects **29/29**, затронутый набор **65/65**, API **37/37**, browser **2/2**, оба live notification worker, frontend, check/drift и sensitive scan — PASS. Схема после ранее проверенных clean upgrade/restore не менялась. Подробности: [PEOPLE_PROJECTS_FINAL_REVIEW.md](PEOPLE_PROJECTS_FINAL_REVIEW.md).

## Projects — локальная реализация, 15.09.2026

Ветка `codex/projects` в checkout `C:\Users\riddl\OneDrive\Документы\AYS Connect актуальный`, HEAD `f13bfce` плюс сохранённые незакоммиченные People-изменения. People Acceptance **PASS** на базе до начала Projects; evidence и отдельный product gap forgotten-password приведены ниже. Реализованы Project/PRJ lifecycle, участники, этапы, контрольные точки, связь с единой Work Task, создание из Work/template, SQL scope, Audit/transactional Outbox, Notification Core, API, UI и защищённые документы. Канонических зависимостей Work Task нет; метрика блокирующих зависимостей остаётся отдельным продолжением согласно ТЗ.

Projects локальный Quality Gate на окончательном коде **PASS**: PostgreSQL backend 444/444, Projects staging API 37/37, браузер 2/2, живой Notification worker и repeat без дубля, frontend build, check/drift/migrate, synthetic clean upgrade/restore, diff и sensitive scan. Требование → проверка → результат → конкретный blocker: [PROJECTS_ACCEPTANCE.md](PROJECTS_ACCEPTANCE.md). В первом релизе blocker отсутствует; Work dependency engine и метрика зависимых блокировок остаются отдельным product-продолжением. Production, реальные аккаунты/credentials, commit/push/deployment не затрагивались.

## People Local Staging Acceptance — 15.09.2026

**PASS** на `main`/HEAD `f13bfce` с незакоммиченными People-изменениями в этом checkout. Утверждено и реализовано правило A/B: новый `pending/active/paused` B сохраняется, завершённый A не открывается, Audit/Outbox фиксируют `reopen_blocked`, Notification Core уведомляет ответственного; уполномоченный сотрудник явно отменяет B и повторяет событие для A. Повторы и конкуренция проверены. Полная таблица «требование → проверка → результат → blocker» — в [PEOPLE_STAGING_ACCEPTANCE.md](PEOPLE_STAGING_ACCEPTANCE.md).

Финальный PostgreSQL 17.11 backend **414/414**, targeted conflict **17/17**, role **163/163**, API **73/73**, browser **5/5**, frontend build, check/drift, новый business upgrade (24 объекта), synthetic restore (179 таблиц/14333 строки/66 media), Notification worker пять причин и sensitive scan — PASS. Forgotten-password остаётся отдельным product gap вне приёмки. Следующая работа — Projects в изолированной ветке на базе этого checkout, с сохранением всех People-изменений. Production, реальные аккаунты/credentials, commit/push/deployment не затрагивались.

## Актуальный People Staging Acceptance — 08.09.2026

PostgreSQL 17.11: 410/410 PASS (handoff v13, skipped 0), API gate25 73/73, полная
синтетическая роль 95 permissions — 163/163, browser gate24 — 5/5, frontend build PASS.
Матрица 95 разрешённых / 26 запрещённых / 30 условных = 151; реальные права не выдавались.
После work_tasks0004: upgrade 24 связанных объекта PASS; restore 179 таблиц/11730 строк/
55 media PASS, ORM/SQL acceptance guard сохранён после restore.
Исправлены mixed view/write и NULL scopes, Admin/legacy lifecycle write paths;
проверены reviewer vs responsible, overdue concurrency и четыре People Email/In-App причины.
Текущий sign-off BLOCKED бизнес-конфликтом возврата старого onboarding при активном новом.
Единая таблица: docs/PEOPLE_STAGING_ACCEPTANCE.md; 95 consumer rows:
docs/OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md. Forgotten-password — отдельный product gap.
Production/аккаунт Юлии/commit/push/deployment не затрагивались.

Дополнительно проверен отказ фактических pre-revocation tokens после restore-c.
Исправлены preflight/exit codes API harness и ожидания worker/Retry-After в browser harness.

## Исторические срезы (не текущий статус)

> Последнее исправление 08.09.2026: task.edit больше не меняет политику приёмки после
> первой публикации. Domain + DB trigger, ORM/bulk/Admin, sticky marker work_tasks0004;
> staging migration PASS, 7 focused tests PASS, live HTTP PASS, full backend 397/397 PASS.
> Прежний тест успешного обхода заменён проверкой запрета. Матрица 95/26/30=151.
> Полный consumer audit, целевая staging-роль и People Acceptance ещё INCOMPLETE.
> Production/аккаунт Юлии/commit/push/deployment не затрагивались.

> Последний срез 08.09.2026: **People Acceptance INCOMPLETE**, access gate BLOCKED.
> Backend 391/391 выполнены, skipped 0 (один тест воспроизводит существующий обход
> обязательной приёмки через task.edit — это не security PASS). API gate13 73/73;
> browser gate12 4/4 уже без Google Fonts interception. Business upgrade 21 связанных
> объектов PASS; restore 179 таблиц/5792 строк/23 media PASS. Матрица: 95 Да/26 Нет/30
> Условно, 151 код. Полная целевая роль не назначалась; task.edit удержан как BLOCKED.
> Реализован локальный Work-event reopen и expiry/overdue notification consumer.
> Production/реальные права/credentials/commit/push/deployment не затронуты.
> Канонический текущий отчёт: docs/PEOPLE_STAGING_ACCEPTANCE.md. Далее исторические срезы.

> Актуальный локальный срез 08.09.2026: PostgreSQL 17.11 **375/375 PASS**, skipped 0,
> Email включён; staging HTTP **73/73**, browser **4/4** (Google Fonts CSS изолирован).
> Два Notification Core падения устранены явным контрактом каналов + новыми тестами.
> HR-review старых/новых значений требует дополнительного scoped sensitive permission.
> Полный People Acceptance **INCOMPLETE/BLOCKED**, матрица доступа ещё DRAFT.
> Ниже исторические срезы; актуальные ограничения и evidence — в
> `docs/PEOPLE_STAGING_ACCEPTANCE.md`, раздел Authoritative checkpoint.
> Production не подключался; commit/push/deployment не выполнялись.

> Последняя перепроверка JWT staging, 08.09.2026: **362/362 PASS**, skipped 0,
> PostgreSQL 17.11, baseline Email off только в test-контейнере. При staging Email on
> два Notification Core теста падают из-за ожидания одной попытки вместо двух каналов;
> это ограничение общего acceptance пока не устранено. Live HTTP suspend → restore:
> старые access/refresh отклонены, новый login/refresh работает. Production в этом
> задании не подключался и не обновлялся; аккаунт Юлии оставлен заблокированным.
> Согласован будущий scope: все подразделения и бизнес-права, без управления
> аккаунтами/ролями/оргструктурой; точный allowlist ещё требует проверки косвенных прав.
> Полный People Staging Acceptance остаётся INCOMPLETE. Ниже — предыдущие срезы.

> 08.09.2026: People LOCAL STAGING ACCEPTANCE поверх `f13bfce` ещё не завершена.
> После согласованного исправления отзыва JWT/Django-сессий: **358/358 PASS**, skipped 0.
> Локально исправлены nullable FOR UPDATE при suspend/restore, повторный expiry-event
> и прямое завершение TASK-шагов без завершённой Task. Изменения не закоммичены.
> Append-only `accounts.0003_user_auth_version`, отдельный synthetic auth-upgrade и
> HTTP smoke PASS. Полные browser A–I/worker/общие upgrade gates ещё не выполнены.
> Production не затронут. Подробности: `docs/PEOPLE_STAGING_ACCEPTANCE.md`.

> 03.09.2026: Phase 2.3 зафиксирована checkpoint `067c60d`; Phase 2.4 Onboarding & Account Lifecycle реализуется локально поверх чистой границы.

**Обновлено:** 03.09.2026

**Ветка:** `main`
**Remote:** `origin` → `https://github.com/JohnyRiddle/ays_connect.git`

## Текущая задача

Phase 2.4 Onboarding & Account Lifecycle — COMPLETE локально; PostgreSQL 17.11 quality gate PASS, готово к отдельному checkpoint.

## Сделано

- production-фазы People Core 1.1A, Tasks 1.1B–1.1D и Service Catalog 1.2A;
- permissions, Audit и transactional Outbox;
- динамические поля, access rules и immutable schema snapshots;
- production `ServiceRequest` с UUID, immutable `REQ-*` нумерацией, snapshot значений и optimistic locking;
- строгий lifecycle NEW → ASSIGNED → IN_PROGRESS → WAITING/RESOLVED → CLOSED, отдельные reopen/cancel операции и histories;
- конфигурируемая маршрутизация через `AssignmentTarget`/`AssignmentResolver`, ручное назначение и история назначений;
- связь заявки с `work_tasks.Task`, manual/template creation и политики завершения execution-задач;
- SQL-level visibility policy, internal API `/api/internal/v1/requests/`, Audit и Outbox;
- PUBLIC/INTERNAL comments, revisions, mentions и soft delete;
- защищённые PUBLIC/INTERNAL attachments с общим storage security pipeline;
- watchers, расширенный PARTICIPATING, privacy-filtered Activity Feed и collaboration summary;
- отдельный SLA domain: версионируемые бизнес-календари, политики, warning thresholds и assignment rules;
- timezone-aware business-time calculator и preview API без изменения runtime заявок;
- SLAInstance, response metric, cycle-based resolution metrics, pause accounting, thresholds и breach history;
- транзакционные hooks ServiceRequest lifecycle, reconciliation и `process_sla` worker;
- SLA status/history API и request list filters;
- immutable escalation policies/bindings, cycle-aware executions и delayed schedules;
- notification intents, watcher/priority/reassignment actions и `process_escalations`;
- проект опубликован в `origin/main` коммитом `bfe8313` до текущего обновления документации;
- добавлены проектные документы передачи контекста и универсальные инструкции Codex.
- добавлен `backend/performance`: registry 30 метрик, исторические факты, версионируемые агрегаты, scoring policies и очередь пересчёта;
- добавлены full/incremental management commands, PostgreSQL `SKIP LOCKED` worker, internal API и SQL-level employee visibility;
- раздел SPA «Эффективность» переведён с legacy analytics на production Performance API;
- добавлен performance worker в pilot/server compose.
- production Work SPA: списки, фильтры, создание, detail и lifecycle actions для Tasks и Service Requests;
- динамическая форма заявки по published schema, PUBLIC/INTERNAL collaboration, SLA/history, watchers и защищённые attachments;
- создание execution Task из заявки, optimistic-lock conflict UX и единая нормализация API-ошибок;
- добавлен read-only lookup AssignmentTarget и человекочитаемые display-поля без изменения доменной логики;
- local pilot обновлён на существующей PostgreSQL БД; direct-route SPA fallback и Playwright smoke 7/7 проходят.
- controlled `RELEASE-GATE-1.6A` scenario восстановлен в отдельных PostgreSQL container/media volume: Employee, Task, Request, execution Task, SLA, Notification и Performance PASS;
- source/restored physical и DB SHA-256 обоих attachment совпадают; protected downloads после restore дают 401 без JWT и 200 с JWT;
- исправлен production Performance enqueue entity-type mismatch и добавлен regression test; baseline 254/254.
- Phase 2.1 расширяет существующий Employee без Person-дубликата: immutable `EMP-*`, historical assignments, manager hierarchy, termination/reactivation, Audit/Outbox;
- append-only migration `employees.0007` сохраняет legacy-поля и создаёт initial history rows для существующих сотрудников;
- два PostgreSQL upgrade rehearsal 0006 → 0007 и полный backend regression 276/276 проходят.
- Work/People frontend возвращён к единой компактной стилистике; все пункты основного меню маршрутизируются, незавершённые разделы имеют штатную заглушку, формы создания Task/Request открываются в правом drawer;
- production frontend build, Compose validation, deployment regression и local-pilot SPA/E2E gate проходят.
- Phase 2.2 расширяет единственную формальную модель `OrgUnit` и добавляет отдельный домен `Team`/`TeamMembership`, не заменяя legacy `FunctionalGroup`;
- добавлены `AssignmentTarget.TEAM`, детерминированные Team Resolver strategies, preview API, scoped permissions, Audit/Outbox и интеграция с увольнением сотрудника;
- PostgreSQL `btree_gist` exclusion constraint защищает всю историю членства от пересекающихся периодов, включая прямые записи вне service layer;
- PostgreSQL 17.11 Phase 2.2 gate: clean migration PASS, upgrade `employees.0007` → current PASS, `23/23` phase tests и `299/299` полный backend regression PASS.
- Phase 2.3 переиспользует `Employee.avatar`, добавляет OneToOne `EmployeeProfile`, типизированную field visibility и отдельный allowlisted `EmployeeDataChangeRequest` с optimistic locking, stale snapshot и запретом self-approval;
- добавлены self-service, directory и review endpoints в существующем `/api/internal/v1/people/`, защищённая выдача avatar, Audit/Outbox и уведомления через действующий Notification Core;
- frontend получил компактную страницу «Мой профиль», completeness, редактирование разрешённых полей и avatar actions; production build PASS.
- PostgreSQL 17.11 Phase 2.3 gate: clean migrations PASS, upgrade `employees.0010 → 0012` PASS, 27/27 phase tests (10 concurrency/security), полный backend regression 326/326 PASS без skipped.
- Phase 2.4 расширяет существующие Employee/User/Invitation/Profile, добавляет безопасную реактивацию, first-login, versioned onboarding templates/snapshots, dependency/responsible resolution, production Task integration и `SKIP LOCKED` reconciliation worker;
- append-only migrations `employees.0013–0015`; clean PostgreSQL 17.11 и upgrade `0012 → current` PASS; 16 Phase 2.4 tests, 10 PostgreSQL concurrency tests и полный regression 342/342 PASS без skipped;
- обнаружены и исправлены PostgreSQL nullable-join `FOR UPDATE` и termination/step deadlock с regression coverage; frontend production build PASS.

## Осталось

- перенести pilot-контур на сервер после получения hostname/network/secrets;
- выполнить расширенные RBAC, полный lifecycle Task/Request/SLA/Escalation/IN_APP/Telegram E2E с ограниченной группой пользователей;
- перед развёртыванием поверх старой базы подготовить план миграции существующих bigint ID к актуальным UUID-моделям либо использовать чистую базу.

## Известные проблемы и риски

- локальный Caddy CA не доверен встроенным браузером; trusted public HTTPS проверяется только на production hostname;

- локальный Docker PostgreSQL volume создан ранним прототипом и не должен обновляться без резервной копии/плана данных;
- production и legacy Tasks временно сосуществуют;
- production Performance API не заменяет legacy `/api/v1/analytics/`; новый SPA использует только `/api/internal/v1/performance/`, а legacy оставлен для совместимости;
- PostgreSQL 17.11 quality gate Phase 1.1D пройден: clean/upgrade migrations, Tasks 45/45, full backend 181/181 и 4 PostgreSQL concurrency tests;
- исправлена PostgreSQL-specific гонка при одновременном добавлении одного Task watcher;
- PostgreSQL 17.11 quality gate Phase 1.2C пройден: clean migrations, upgrade-клон Phase 1.2B → `0004`, 121 тест и 7 PostgreSQL concurrency/atomicity проверок;
- PostgreSQL 17.11 quality gate Phase 1.3A пройден: clean/upgrade migrations и 129 backend-тестов, включая 8 SLA domain tests;
- PostgreSQL 17.11 quality gate Phase 1.3B пройден: clean/upgrade migrations и 139 backend-тестов, включая 18 SLA tests и concurrency gate;
- PostgreSQL 17.11 quality gate Phase 1.3C пройден: clean/upgrade migrations и 154 backend-теста, включая 33 SLA/escalation tests, concurrency и E2E actions;
- устранена PostgreSQL-specific несовместимость `SELECT FOR UPDATE` с nullable outer join при публикации SLA policy;
- Docker Desktop и Linux engine доступны; gate выполнен в изолированном PostgreSQL 17 container.

## Рекомендуемый следующий шаг

Получить параметры production server и выполнить server-dependent gates. Не объявлять Work Core v1.0 до trusted HTTPS, reboot, Telegram и real-user UAT.

## Команды проверки

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test

cd ../frontend
npm run build

cd ..
docker compose run --rm backend python manage.py test
```
