# Объекты — финальное review/acceptance, 08.10.2026

## 09.10.2026 — acceptance рабочей восстановленной копии

**Code/synthetic acceptance PASS; O0 inventory PASS для подтверждённого snapshot; restored upgrade compatibility PASS. Legacy mapping / transfer N/A: рабочие Facility=0, Zone=0. Production readiness CONDITIONAL / NOT VERIFIED полного выпуска, deployment NOT PERFORMED.** Предоставленный SSH identity снял DATA BLOCKED для документированного текущего источника: PostgreSQL 17.11, все восемь target models=0; 101 applied/0 pending/0 unknown migrations; 407/407 runtime Python/requirements files совпадают с main `64f85fa…` после нормализации EOL.

PASS ограничен согласованным dump SHA из readiness report, получение завершено 2026-10-09T06:53:54.581111+00:00; время открытия PostgreSQL snapshot отдельно не записано.

Точный runtime код: `73a8092b4b0675daf2f0a6ab11fb8e090226f58c` **плюс локальные две URL waits в objects.spec.ts**. Backend/UI runtime и миграции unchanged; browser-test SHA `0d19dad80147e1dbe658db52842ee84f32a5ca287f30f12574c8c3f5195facc9`. Полный 585 regression не повторялся; 32/32 transaction-rollback API checks на upgraded source copy, browser **6/6, 29.9s, exit 0** на окончательном test diff. Исправлена ранняя фиксация UUID до navigation, query created=1 допустим; Windows fixture encoding исправлено только в копии. Промежуточные failed browser attempts не объявляются PASS.

Baseline 196 tables/1950 rows → upgrade 198/1973; пять append-only migrations; 192 old tables identical, четыре ожидаемых catalog/migration delta; grants unchanged. Original restore fingerprints PASS; исходные 2 Work/1 Project сохранились. Post-test differences только number counters от test creation; новых source users/passwords/roles не меняли. Значения/DB/private artifacts не входят в Git. [Полное evidence и команды](OBJECTS_RELEASE_READINESS.md), [O0](OBJECTS_O0_ACCEPTANCE.md). Fresh maintenance DB/media/off-host restore перед выпуском остаётся отдельным operational gate; merge/deployment не выполнялись.

## История: актуализация 09.10 до предоставления identity

Функциональность реализована. **Code / synthetic acceptance — PASS** для опубликованного checkpoint `73a8092b4b0675daf2f0a6ab11fb8e090226f58c`, draft [PR #1](https://github.com/JohnyRiddle/ays_connect/pull/1); текущая base main `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`. Все 36 source SHA-256 совпадают с manifest; код и миграции не менялись, полный gate повторно не запускался. Новые локальные изменения только документационные.

**O0 DATA BLOCKED; compatibility на восстановленной рабочей копии, реальные mapping, перенос и production readiness — NOT VERIFIED.** Повторный SSH с настроенными identities и существующим deploy-key не прошёл; подтверждённого актуального backup нет. Новых inventories/upgrade/browser на реальных данных нет. [O0 evidence](OBJECTS_O0_ACCEPTANCE.md), [release readiness и следующий шаг](OBJECTS_RELEASE_READINESS.md). Production deployment NOT PERFORMED. В этой задаче commit/push/merge не выполнялись; формулировки ниже о ещё не созданном checkpoint описывают состояние review 08.10 до его отдельной публикации.

## Историческое финальное review 08.10

**READY FOR CHECKPOINT. Функциональность реализована; synthetic acceptance — PASS. O0 DATA BLOCKED. Реальные mapping, перенос и production readiness — NOT VERIFIED.** Ветка `codex/objects`, база `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`, отдельный managed worktree. Commit/push/merge/deployment не выполнялись.

## Три отдельных результата

1. **Новый функционал:** O1/O3/O4 реализованы; пользователь с разрешёнными правами создаёт Location-объект, назначает Employee, добавляет зоны, меняет lifecycle, просматривает policy-scoped связанные данные. Core/Audit/Outbox/idempotency и bypass guards проверены PostgreSQL тестами; UX проверен desktop/mobile browser.
2. **Синтетическая совместимость:** append-only schema, чистая установка, baseline upgrade с People/Work/Projects/Facility/Zone связями, repeat plan и backup/restore — PASS. Сохранены синтетические UUID, непустой code, свободные location_type и legacy FK. Это технический gate, не принятие реальных данных.
3. **Актуальная рабочая БД:** не проверена. O0 DATA BLOCKED; неизвестны production Location/Facility/Zone counts, mapping, JSON/string/GFK semantics, мультиюридические исключения и реальные grants. Реальный mapping/dry-run/backfill/repeat/conflict log не реализованы без инвентаризации. Пустые локальные БД не заменяют рабочую. [Подробное O0 evidence](OBJECTS_O0_ACCEPTANCE.md).

## Матрица требований

| Требование | Проверка | Результат | Evidence | Blocker |
|---|---|---|---|---|
| O0 read-only | два PostgreSQL snapshots, read_only flag/rollback, inventory unit | PASS механизма, 8/8; DATA BLOCKED актуальных данных | deployment/objects_inventory.py, test_objects_inventory.py, O0 report | Подтверждённая актуальная копия/read-only доступ |
| Минимальная/полная/scoped create | поля, связи, timezone, NULL/hidden grants, initial responsible | PASS synthetic | organizations/test_objects.py; browser full create | Рабочие scope exceptions неизвестны |
| Idempotency и транзакция | same/different payload, revoked replay, concurrent repeat, code uniqueness, Audit/Outbox rollback | PASS synthetic | Objects PostgreSQL; browser committed-response-loss retry с одинаковым ключом | — |
| Дубли/privacy | normalize+parent, hidden object exclusion, explicit confirm | PASS synthetic | backend и duplicate browser | Реальные duplicate clusters ждут O0 |
| Дерево | invalid parent, 34-zone chain cycle, concurrent mutual move, source/target policy | PASS synthetic | test_zones_invalid_parent_stale_version_and_cycle, concurrency | Классификация старого дерева не выполнена |
| Lifecycle/ответственность | seasonal без People/Work effects, close/archive blockers, restore без назначения, termination/reactivation и race | PASS synthetic | Objects PostgreSQL; browser lifecycle/archive/restore | Реальные lifecycle semantics неизвестны |
| Версии/ошибки | stale 409, hidden relations 404, malformed filters 400, sanitized 500 | PASS synthetic | backend; browser stale edit сохраняет ввод и повторяет после refresh | — |
| Security | SQL list/search/tree/lookups/counts, IDOR, mixed view/write, unsupported scopes, Admin/old API/ORM guards | PASS synthetic | Objects PostgreSQL | Актуальные grants не инвентаризированы |
| Associated policies | effective Assignment/People, Task/Request/Project visibility и counts; direct/participating Project | PASS synthetic | backend API tests и full regression | Production data semantics не проверены |
| Consumer archive guard | новые FK bindings/реактивация запрещены; historic edits/PerformanceFact сохранены | PASS synthetic | organizations/test_objects.py; PG triggers | Рабочие неструктурированные связи неизвестны |
| O2 сохранность schema/FK | clean install, baseline upgrade, empty repeat plan | PASS synthetic | deployment/objects-staging/verify_upgrade.py | Реальные mapping/dry-run/conflicts BLOCKED |
| Backup/restore | pg_dump custom + pg_restore --exit-on-error; read-only сравнение | PASS synthetic | verify_restore.py; hashes ниже | Актуальный production restore point не проверен |
| O3 registry/card | URL filters/reload, create/edit/zones/responsibles, history, direct links, focus/mobile/network/conflict | PASS synthetic | frontend/tests/e2e/objects.spec.ts, production build | Большие lookup каталоги: ограничения ниже |
| O4 Work/Requests/Projects | existing forms с выбранным UUID; фактические create Task/Request/Project и related lists | PASS synthetic | первый browser scenario, backend associated tests | — |
| O5 backend regression | fresh PostgreSQL DB, все приложения | PASS 585/585 | Django runner: 163.202s, exit 0 | Не production DB |
| Objects concurrency/security final | после финальных scope/create/privacy/restore исправлений | PASS 36/36 (в составе полного 585 gate) | окончательный organizations/test_objects.py, включая 4 concurrent tests; full runner exit 0 | — |
| Frontend final build | tsc + Vite 8.2.0, 1814 modules | PASS | index-DwZChlut.js, index-BBC6vgjQ.css | — |
| Browser final | Chromium, ordinary/denied personas; desktop и 390×844 | PASS 6/6, 28.9s | Playwright objects.spec.ts | Synthetic only |
| Framework/drift/config/diff | manage.py check, makemigrations --check --dry-run, dedicated Compose config, diff --check | PASS | 0 issues, No changes detected, exit 0 | — |

Все текущие PASS выше относятся к окончательному коду review 08.10.2026. 36 Objects и 4 concurrency входят в 585, это не отдельные слагаемые. Backend runtime не менялся после этого gate; после frontend build изменён только browser helper/добавлен synthetic editor fixture, runtime UI совпадает с финальным browser gate.

## Найденные и исправленные дефекты

- Create/capabilities требовали create, но не видимость результата: теперь требуются совместимые create **и view** contexts. location.manage не подразумевает view. Domain mutations требуют view/write; inactive User grants закрыты.
- Scoped старый Location API отдавал скрытые parent/LegalEntity/OrgUnit UUID; read-only Admin мог показывать имена этих FK. API теперь маскирует их, Admin исключает недоступные связанные поля. Writes старого API/Admin по-прежнему запрещены.
- Restore зоны под архивным объектом попадал в DB exception/500: доступность всей parent-цепочки проверяется сервисом, возвращается 400 с rollback.
- UI PATCH отправлял все поля: скрытый OrgUnit мог очиститься, а refresh после конфликта мог перезаписать чужое неизменённое пользователем имя. Теперь отправляются только действительно изменённые поля; browser проверяет сохранность OrgUnit/LegalEntity и concurrent name.
- Ответ позднего запроса старой вкладки мог заменить текущую вкладку: serial guard принимает только актуальный related response.

Новые backend проверки: visibility-required create/manage compatibility, inactive actor, old API/Admin relation masking, restore under archived parent. Browser добавляет редактора с location.view/edit и без organization/HR grants. Initial расширенный browser запуск упёрся в штатный login throttle (429): helper теперь один раз аутентифицирует каждую из трёх персон на worker и переиспользует токены. Production throttle/settings не ослаблены. Финальный gate 6/6 после исправления; промежуточный результат не PASS.

Исторические gate 02.10.2026 (581/32/5) заменены текущими 585/36/6; не используются как доказательство исправленного кода. Исторический --keepdb запуск с очищенным миграционным fixture catalog и Objects teardown с открытыми thread connections также не считаются PASS; полный текущий gate создаёт свежую БД и завершился exit 0.

## Синтетический install/upgrade/restore

Schema migrations при review не менялись. Install/upgrade/dump/restore выполнены 02.10.2026; 08.10.2026 свежая тестовая БД полного regression прошла все migrations и read-only verify_restore.py повторно подтвердил обе сохранённые БД/relationships/защитные триггеры. Это не новый production restore.

Отдельный PostgreSQL 17.11 container `ays-objects-db`, без опубликованного DB port и без production network. Базы `objects_clean`, `objects_upgrade`, `objects_restored` созданы только для этой задачи. Clean migrate — PASS. Upgrade строит baseline organizations 0003/access_control 0002 и остальные текущие приложения, создаёт явно синтетические старые Location/EmployeeAssignment/Task/Project/Facility/Zone/EmployeeFacility, затем применяет latest append-only migrations; никакой production mapping не выполняется.

Upgrade dump восстановлен в objects_restored. Для обеих БД read-only verify дал одинаковые:

- 198 таблиц, 1127 строк;
- data SHA-256: `a39bcd5c98df09f362a4971ed1c59d80055062f819ae83e4dcca51d1f5374d16`;
- trigger SHA-256: `7a4c6fc702ce5473c6d2bc09c5a91575f4c23030cd2260649ccc2a730ed3ed5d`;
- relationships PASS, read_only=true.

Dump остался в `/tmp` выделенного контейнера, в Git БД/dump/media/секретов нет. Это не production backup/restore acceptance.

## Воспроизводимые проверки

Из worktree, в выделенном synthetic environment. Пример подключения ниже содержит только известные синтетические credentials, никогда не подставлять рабочую БД.

```powershell
docker run --rm --network none --mount 'type=bind,source=C:\Users\riddl\.codex\worktrees\objects\AYS Connect,target=/workspace,readonly' --workdir /workspace aysconnect-backend:latest python -m unittest discover -s deployment -p test_objects_inventory.py -v

docker run --rm --network container:ays-objects-db --mount 'type=bind,source=C:\Users\riddl\.codex\worktrees\objects\AYS Connect\backend,target=/app' --workdir /app -e DATABASE_URL=postgresql://objects:synthetic_objects_only@127.0.0.1:5432/objects aysconnect-backend:latest python manage.py test --noinput

docker exec ays-objects-api python manage.py check
docker exec ays-objects-api python manage.py makemigrations --check --dry-run
docker exec ays-objects-ui npm run build

docker run --rm --add-host host.docker.internal:host-gateway --mount 'type=bind,source=C:\Users\riddl\.codex\worktrees\objects\AYS Connect\frontend,target=/app' --workdir /app -e AYS_E2E_BASE_URL=http://localhost:13031 -e AYS_E2E_HOST_GATEWAY=192.168.65.254 -e AYS_OBJECTS_API_URL=http://host.docker.internal:18081 ays-projects-browser:integrated npx playwright test objects.spec.ts --workers=1

docker compose -p ays-objects-synthetic -f deployment/objects-staging/compose.yml config --quiet
git diff --check
```

Gate использовал существующие локальные backend/browser images и bind актуального worktree кода; production images не менялись. Для независимого запуска нового Compose требуется построить image и дождаться synthetic init. Upgrade/restore scripts проверяют имя выделенной БД и не подходят к рабочему DSN. Desktop/mobile screenshots в ignored frontend/test-results, визуально проверены; JWT traces/персональные выгрузки в Git отсутствуют.

## Ограничения и checkpoint

O1/O3/O4 и O5 local — готово; O2 synthetic schema — PASS; O0 и O2 real-data — DATA BLOCKED. Старые unclassified записи не включены в Objects registry, не переклассифицированы и сохраняются в read-only Location API. Реальные mapping, перенос и production readiness — **NOT VERIFIED**. Географические grant исключения и мультиюридические преобразования не разрешены предположениями. UI Employee lookup ограничен 200, UI move — первой страницей; для крупных каталогов нужен UX поиска (move API поддерживает page/search).

Точный состав diff, SHA-256 исходников, исключения и checkpoint message: [OBJECTS_CHECKPOINT](OBJECTS_CHECKPOINT.md). Git worktree содержит новые и изменённые backend/frontend/deployment/docs files, всё unstaged/uncommitted. Исходный checkout с прежними незакоммиченными файлами сохранён на main. Предлагаемый code checkpoint: `feat(objects): add Location-based objects module and synthetic acceptance`. Commit выполнять только по отдельному запросу; production release остаётся заблокирован.

08.10.2026 повторно запущен read-only fingerprint (каждая команда exit 0):

```powershell
docker run --rm --network container:ays-objects-db --mount 'type=bind,source=C:\Users\riddl\.codex\worktrees\objects\AYS Connect\backend,target=/app,readonly' --mount 'type=bind,source=C:\Users\riddl\.codex\worktrees\objects\AYS Connect\deployment\objects-staging,target=/review,readonly' --workdir /app -e PYTHONPATH=/app -e DATABASE_URL=postgresql://objects:synthetic_objects_only@127.0.0.1:5432/objects_upgrade aysconnect-backend:latest python /review/verify_restore.py
docker run --rm --network container:ays-objects-db --mount 'type=bind,source=C:\Users\riddl\.codex\worktrees\objects\AYS Connect\backend,target=/app,readonly' --mount 'type=bind,source=C:\Users\riddl\.codex\worktrees\objects\AYS Connect\deployment\objects-staging,target=/review,readonly' --workdir /app -e PYTHONPATH=/app -e DATABASE_URL=postgresql://objects:synthetic_objects_only@127.0.0.1:5432/objects_restored aysconnect-backend:latest python /review/verify_restore.py
```

Synthetic fixture текущего gate подготовлен через `docker cp deployment/objects-staging/prepare_synthetic.py ays-objects-api:/tmp/prepare_synthetic.py` и `docker exec -e PYTHONPATH=/app ays-objects-api python /tmp/prepare_synthetic.py`, затем API/UI перезапущены. Fixture ограничен выделенной БД objects. Docker Desktop восстановлен из установленного локального runtime; рабочая БД и production deployment не затрагивались.
