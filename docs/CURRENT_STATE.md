# Текущее состояние AYS Connect

> 01.09.2026: Phase 1.6C COMPLETE from checkpoint `0792ec2`. Employee Directory, hash-only invitations, atomic activation, controlled registration and account administration pass PostgreSQL 264/264, Playwright 15/15, pilot and isolated backup/restore gates. Phase 1.6B has not started.

**Обновлено:** 01.09.2026

**Ветка:** `main`
**Remote:** `origin` → `https://github.com/JohnyRiddle/ays_connect.git`

## Текущая задача

Phase 1.6C — COMPLETE. Phase 1.6 LOCAL GATES PASS; production/server Phase 1.6B remains PENDING.

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
