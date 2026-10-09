## 09.10.2026 — release STOP до maintenance; temporary persona закрыта

Повторная фактическая storage проверка обнаружила незакрытый обязательный gate: действующий `ays-connect-production_backup_data`, 24 файла / 8124 KiB, находится на `/dev/sdb1 ext4`, без подтверждённого crypt-слоя. EFS off-host/LUKS rehearsal storage не защищает этот действующий volume. Перед GO требуется проверенное переключение всего periodic backup storage на encrypted mount с сохранением bytes/UID/GID/modes, возобновлением без запуска retention и отказом записи при отсутствии encrypted mount. Пользовательский downtime **0 секунд**; production init, merge, deployment и новый release backup не выполнялись. Прежняя версия production сохранена.

Temporary production persona User 6 / Employee fa09c72e-5a01-49f4-a7da-8e32856ea903 штатно закрыта после STOP: active assignments 0, User inactive, Employee terminated/inactive; audited session revocation, фактический access до закрытия 200, тот же access после 401, refresh 401, новый login 401. Реальные User values не менялись, audit/rows сохранены. Live denied/scoped Objects acceptance **NOT PERFORMED**, прежний rehearsal PASS относится только к копии; этот cleanup PASS не является разрешением пропуска live gate. Для следующей попытки проверить статус persona и свежий baseline заново; не использовать уже отозванные credentials.

Production после STOP: 11 running containers, backend и 6 workers healthy, backup running/unpaused, оба HTTPS домена и live/ready — 6/6 HTTP 200. Исходные dirty bytes сохранены. Snapshot O0/upgrade PASS и legacy N/A остаются ограничены snapshot 09:49 UTC; production readiness **CONDITIONAL**, deployment **NOT PERFORMED**. Разрешение release сохраняется после устранения STOP, повторное разрешение предусмотренных шагов не требуется.

# Объекты — финальное review/acceptance, 08.10.2026

### 09.10.2026 — encrypted preflight и временная live persona подготовлены

Разрешены one test User/Employee и минимальные audited scope assignments с обязательным revoke/terminate/token/session denial, без изменения реальных grants. Production persona User 6 / Employee fa09c72e-5a01-49f4-a7da-8e32856ea903 создана non-staff/non-superuser, пока 0 grants; baseline теперь Users 5/Employees 4. Owner штатно вошёл на SSH-only localhost:13041. Новый I:\AYS Connect EFS off-host destination, DPAPI key copies на отдельном физическом F: с фактическим age/LUKS recovery check, server LUKS2 и relocation retained backup/restore volumes с SHA/UID/GID/mode сохранением подготовлены. BitLocker/off-device recovery/free-space remanence не заявлены PASS. Persona scenario/credential revocation rehearsal PASS только copy; production rights/cleanup ещё NOT PERFORMED. Positive scoped create — zone в разрешённом smoke parent; root LegalEntity scoped-create N/A без разрешённого контекста. Fresh rollback point/restore/init/live tests впереди; readiness CONDITIONAL, deployment на момент preflight NOT PERFORMED. [Evidence, scope и recovery constraints](OBJECTS_RELEASE_READINESS.md).


### 09.10.2026 — разрешённый release: STOP до maintenance

Merge/deployment не начаты: обязательные gates не закрыты. Актуальный production: Users 4/Employees 3 против snapshot 3/2; Role/RolePermission/EmployeeRole fingerprints прежние (1/125/1), source runtime 407/407 × 7 containers прежний, migrations 101, восемь целевых справочников отдельно 0. Active non-superuser persona отсутствует; scoped/denied production acceptance не заменяется owner superuser или anonymous 401. Шифрование всех raw/restore storage и независимая key custody не доказаны. Штатная original-origin сессия ivan@ays-connect.ru есть, SSH-only origin login ещё NOT VERIFIED. Pinned images/override PASS; прежние 13 containers/images и HTTPS 6/6 200 сохранены; downtime этой попытки 0. Release/merge SHA нет, RC220ffac / PR#1 draft остаются. Recovery owner Иван, retention 90 дней/delete только им. Разрешение предусмотренного runbook цикла сохраняется после устранения блокеров; PASS непроверенным сценариям не присваивается. [Точные STOP evidence и условия](OBJECTS_RELEASE_READINESS.md).


### 09.10.2026 — финальный release package RC 220ffac

Exact-RC frontend image и backend/worker/init override подготовлены без переключения production; prod-flavoured bundle через SSH-only isolated ingress — browser 6/6 PASS. Runtime/schema неизменны относительно checkpoint 73a8092; full regression не повторён. Snapshot O0/upgrade PASS относится только к 09:49 UTC, legacy mapping/перенос N/A только snapshot. Recovery owner — пользователь; retention 90 дней, удаление только им; P1/office/Asia/Novosibirsk/один object+zone+archive согласованы. Отдельная age encrypted copy существующего backup проверена, но raw backup/volumes encryption и независимая key custody не доказаны. Нет active denied/scoped production persona: требуется существующая persona или явное принятие ограничения. Новый production backup/init/smoke/deployment, commit/push/merge не выполнялись. Production readiness CONDITIONAL. GO/STOP, точные digests/override, разрешённый delta smoke и rollback с сохранением новых данных: [OBJECTS_RELEASE_READINESS.md](OBJECTS_RELEASE_READINESS.md).


## 09.10.2026 — fresh frozen DB/media snapshot и full actual init RC220ffac

**O0 PASS, off-host DB/media independent restore PASS, full actual init/upgrade PASS, API32/32 (19.078s), browser6/6 (29.5s); legacy mapping/transfer N/A этого snapshot. Production readiness CONDITIONAL; production write-smoke/deployment NOT PERFORMED.** RC `220ffac89568a0e7b2aa493a4b599e0aa1946772` runtime/schema unchanged; test SHA0d19dad… unchanged. Полный 585 gate от08.10 не повторялся.

Новый frozen backup capture 09:49:39.874375–09:49:41.107101 UTC, DB SHA `df1943c4e0286cb1d0cfe55ade14ce636187138134f137d1c0d1e9762c777504`, media SHA `63e15ba15ac544c6de0d349438e999d5025d7b1ff3accf7bf1e89577f4225d63`. Source101/0/0, восемь target counts0, current grants/FK/semantic scan перепроверены (505fields/5477values; explicit nonemptyrefs0; null location_id keys2; scan limits retained). Прежний production возобновлён до copy rehearsal: proxy stopped193.697s / full maintenance201.602s, HTTPS/health/workers PASS; реальные source users/roles/grants/schema unchanged.

Из off-host файлов restored196tables/1950rows + media4files/40bytes, fingerprints совпали. Полный фактический Compose init **в копии**: пять migrations, seed_permissions162, collectstatic163, chown; after198/1973, old192tables unchanged, только четыре разрешённых catalog/migration delta, labels renamed0, реальные RolePermission/EmployeeRole/User privileges unchanged, repeatplan[]/check/drift PASS. Independent original restore unchanged. Новые copy test personas: legacy-role125grants create/replay PASS, исходные2Work/1Project читаются test-admin; API32 внутри rollback и browser6PASS. После тестов изменились только три number-counterrows; бизнес-строки/media сохранились. Concurrency4 evidence — прежний585gate, не новый restore run.

[Full evidence, exact source/version/times/SHA/commands, limitations и remaining release conditions](OBJECTS_RELEASE_READINESS.md). Copy workers/external egress/production mounts исключены; rehearsal containers/tunnels остановлены, volumes/backups сохранены. Production release/write-smoke, commit/push/merge не выполнялись. Backup этого snapshot не считается автоматически актуальной rollback точкой после открытия writes; frontend production artifact/ingress/recovery policy и отдельное разрешение остаются gates. Предыдущие разделы ниже описывают прежний online snapshot.

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
