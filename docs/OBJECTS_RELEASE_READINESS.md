# Objects — release readiness, 09.10.2026

**O0 inventory — PASS для подтверждённого рабочего snapshot. Upgrade / сохранность — PASS. Legacy mapping и перенос — N/A: Facility=0, Zone=0. Production readiness — CONDITIONAL / NOT VERIFIED; deployment — NOT PERFORMED.**

## Точная версия

Runtime checkpoint `73a8092b4b0675daf2f0a6ab11fb8e090226f58c`, ветка `codex/objects`; draft [PR #1](https://github.com/JohnyRiddle/ays_connect/pull/1), main/base `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`, 46 checkpoint files. Перед работой все 36 raw SHA совпали с [manifest](OBJECTS_CHECKPOINT.md).

Release candidate: отдельный commit `docs(objects): record production snapshot upgrade acceptance`, дочерний к этому checkpoint, включает **пять обновлённых документов, этот новый readiness/runbook и две дополнительные assertions ожидания URL в frontend/tests/e2e/objects.spec.ts**. Его точный SHA — commit, содержащий этот документ (PR head после публикации); self-referencing SHA в файл не записывается. Runtime backend/UI и миграции не менялись. Browser-test raw SHA `0d19dad80147e1dbe658db52842ee84f32a5ca287f30f12574c8c3f5195facc9`; текущий fingerprint тех же 36 source paths `0f46cef8e73087a60357c6b44ab6b519d65935475f7c1eaf47208f6ea4acf09a`. Старый manifest остаётся историческим manifest checkpoint; единственное объяснённое source расхождение — browser test.

Code/synthetic acceptance — PASS: runtime regression 08.10 PostgreSQL 585/585 (Objects 36, concurrency 4), inventory 8/8, frontend build/check/drift/install/upgrade/restore PASS. Полный gate не повторялся: общие services/permissions/schema и runtime UI не менялись. Изменённый browser test повторно проверен 6/6 на восстановленной рабочей копии; PASS относится к окончательному локальному diff.

## Подтверждённый источник

Работающий `ays-connect-production` на документированном `109.237.109.58:40222`, `/opt/ays-connect`. Пользователь предоставил существующий SSH identity; подключение с BatchMode/IdentitiesOnly/StrictHostKeyChecking прошло. Содержимое ключа, env и credentials не выводилось. Предыдущие отказы default/deploy identity — исторические, DATA BLOCKED снят для этого источника.

Источник инвентаризации — соединение установленного backend: host `db`, database `ays_connect`, PostgreSQL **17.11**, READ ONLY / REPEATABLE READ. Проверены statement_timeout=60s, lock_timeout=5s; idle timeout=60s задан через PGOPTIONS. Source runtime сверил восемь моделей со схемой до чтения: missing columns/tables=0. Новые Objects модели к production не подключались.

Backend container ID `f66b6b84e6bb5f9b032183635a0ed7149487dc902fdf8858d7ee4f36287bbbb2`; image `sha256:182f57f5ad5340e055edf113e66ab4ce7886a0995c48b324bcb826224d6e9b6f`. **407/407** Python/requirements исходников runtime после нормализации CRLF совпали с main `64f85fa…`; normalized runtime fingerprint `eda2c4df1eb9f2af4cd3ded73fb57276e22289d07e0f1a064cc7bfb1fb8df1b8`. Это доказательство backend версии по source и image, а не одному health marker; полнота совпадения всего frontend deployment этим сравнением не утверждается.

Source applied migrations **101**, pending **0**, unknown **0**. Релевантные cutoffs: organizations 0003; access_control 0002; accounts 0003; employees 0015; work_tasks 0004; projects 0008; iiko 0007. В конце source по-прежнему имел 101 applied migrations и нулевые counts всех восьми моделей.

Статический `o0_status` инвентаризатора остаётся `BLOCKED_PENDING_DATA_PROVENANCE_AND_MAPPING_CONFIRMATION`: сам скрипт не подтверждает provenance и бизнес-решения. Итоговый PASS здесь — отдельное заключение после подтверждения источника, source fingerprints, свежего dump и доказанного empty legacy; не автоматический PASS по exit 0.

Fresh `pg_dump --format=custom --no-owner --no-acl` streamed по SSH в новый защищённый каталог **вне Git/OneDrive** с ACL текущего пользователя. Получение dump завершено **2026-10-09T06:53:54.581111+00:00**, размер **1 024 854 bytes**, SHA-256 `041c5fc9f2e6b7dd14b4c78909d50dd27afb6ff8d0e0f0a54126444816c3521b`. Это timestamp завершения получения артефакта, а не отдельно измеренное время открытия PostgreSQL snapshot: время открытия транзакции pg_dump не записано. O0 PASS относится к source snapshot/этому dump SHA и прочтениям 09.10, не к произвольному будущему состоянию production. Это online согласованный DB snapshot, не maintenance DB/media release backup. Исторический backup 10.09 не использовался. Исходный dump не изменялся.

## Инвентаризация актуального snapshot

| Модель | Count | Пустые поля / дубли / дерево / связи |
|---|---:|---|
| Location | 0 | Пустые/unknown types, коды, родители, активные потомки, LE и OrgUnit — N/A: строк нет |
| Facility | 0 | Legacy mapping N/A |
| Zone | 0 | Legacy mapping и zone/root mismatch N/A |
| Company | 0 | N/A |
| Region | 0 | N/A |
| Cluster | 0 | N/A |
| LegalEntity | 0 | Действующие мультиюридические исключения N/A |
| OrgUnit | 0 | N/A |

Все целевые FK counts равны 0; обнаружено 71 FK field, errors=0. В этой БД есть Users=3, Employees=2, Work Task=2, Project=1, ServiceRequest=0, iiko KnownGuest=2, CardCreation=0. Эти агрегаты не раскрывают имён или содержимого.

Реальные grants: один global location.view и один global location.manage, одна EmployeeRole. Роли/аккаунты production не менялись. В копии проверен новый тестовый пользователь с 125 grants существующей роли: capabilities/create/replay PASS, права не назначались реальным пользователям. Также проверены scoped/denied personas; назначения ответственности не выдают прав.

На исходной восстановленной версии в READ ONLY просмотрено **505** JSON/string/text полей, **5477** непустых значений. Явных объектных ключей/ID/UUID-паттернов — **0**, audit object references — **0**, GenericForeignKey fields — **0**. Ни значения, ни ПДн в stdout/Git не выведены. Ограничение: автоматический скан не доказывает отсутствие произвольных encoded/name-only ссылок; нет существующих целевых объектов, с которыми их можно сопоставить. Свободные тексты не считаются основанием CREATE_NEW. Кандидатов реального mapping нет по причине отсутствия legacy, а не из-за неподтверждённого matching.

## Изолированная копия и upgrade

Выделенный Docker contour/project label `ays-objects-o0-b5d1348f6936`, новые `-net` (**internal=true**) и `-pg` volume; DB/API containers `-db` / `-api`. Существующие DB/volumes не удалялись и не перезаписывались. Docker CLI использован вместо Compose init: ни bootstrap, ни workers не запускались. Базы `objects_copy` и отдельно `objects_original` созданы с новыми именами. Нет public ports, production network/Redis/media mounts и внешнего выхода. Временный signing secret и DB credentials новые; restored sessions не открыты наружу. Исходный image использован только как dependency runtime; `git archive HEAD backend` скопирован в отдельный inert API container, production code не заменялся.

Baseline до подготовки любых тестовых personas: **196 таблиц / 1950 строк**, защищённые SHA каждого table JSON-row set. План содержал ровно:

```text
access_control.0003_alter_rolepermission_scope
organizations.0004_location_address_location_business_status_and_more
organizations.0005_objects_guards_and_permissions
organizations.0006_responsibility_service_guard
organizations.0007_binding_lifecycle_guards
```

После upgrade: **198 таблиц / 1973 строки**. 192 исходных таблицы совпали побайтово по row fingerprints. Допустимые служебные изменения:

| Таблица | До | После |
|---|---:|---:|
| access_control_permission | 166 | 174 |
| auth_permission | 740 | 748 |
| django_content_type | 185 | 187 |
| django_migrations | 101 | 106 |

Новые таблицы — organizations_locationidempotency и organizations_locationresponsibility; добавлены Objects fields/sequence/triggers. RolePermission и EmployeeRole fingerprints совпали; новые grants не появились. Legacy таблицы остались. UUID/code/free types/FK не изменялись; старых Location нет, поэтому сохранность непустых Location значений здесь N/A, отдельно доказана synthetic upgrade fixture.

`check`: 0 issues; `migrate --check`: PASS; `makemigrations --check --dry-run`: No changes detected; повторный migration plan пуст. Исходный dump независимо восстановлен в **objects_original**: все 196 tables / 1950 rows и их fingerprints совпали с baseline. Upgraded dump не подменяет этот restore proof.

## Проверки на восстановленной структуре

- **32/32** ObjectsTests methods выполнены внутри отдельных atomic rollback на objects_copy, без Django test DB/flush. Новые test accounts/records откатились; concurrency 4 здесь не повторялись, их evidence — checkpoint 585 gate.
- Проверены create/idempotency/payload conflict, scopes/list/detail/lookup/counts, hidden related data, Audit/Outbox rollback, версии/дерево/циклы, зоны/ответственные/lifecycle, старый API/Admin/ORM bypass, archive bindings и Work/Requests/Projects policies.
- Новая test persona с grants существующей роли: create/replay PASS без superuser bypass. Исходные 2 Work и 1 Project после upgrade доступны отдельной маркированной test-admin persona. Исходные строки этих consumers и их relationships сохранились. Это не обещание доступности всех проектов любой роли; текущие policies и персональные scopes сохраняются.
- **Browser 6/6 PASS, 29.9s, exit 0**, desktop/mobile, на upgraded copy: existing final build index-DwZChlut.js / index-BBC6vgjQ.css; локальный Edge Chromium, Playwright, UI loopback 13031, API через SSH loopback tunnel 18081 к internal API. Tests используют только новые synthetic accounts. Email/Telegram/iiko отключены; external network blocked; restored Outbox workers не запускались.
- Первые browser attempts не PASS: UTF-8 fixture первоначально прочитан Windows default encoding; исправлены исключительно новые тестовые labels. В browser test выявлено раннее чтение URL до React navigation: добавлено ожидание pathname UUID в двух местах, допустим query `created=1`. Последний полный 6-test run относится к этому окончательному diff. Runtime модуль не исправлялся: дефект был в тестовой синхронизации.
- После тестов все исходные business rows сохранены; ожидаемо изменились только три служебных counter rows в employees_employeenumbersequence, projects_projectnumbersequence, work_tasks_tasknumbersequence от тестовых созданий. Эти изменения принадлежат тестовой подготовке, **не миграциям**. Ни source passwords, ни реальные profiles/tasks/projects не изменились. Новые test entities/Audit/Outbox — только в копии.

Фактический каталог объектов пуст; больших lookup проблем на нём не воспроизведено. Предел Employee UI lookup 200 и первая страница move UI остаются известными ограничениями, не доказанными проблемами текущего snapshot. Синтетические legacy строки тестов не объявляются реальными и не служат основанием mapping.

## Команды и воспроизведение

Все DB-changing команды ниже относятся **только к новой isolated copy**, не production. Paths/credentials заменяются настроенными безопасными значениями; env не печатать. Записывать новый source timestamp/SHA, не переиспользовать существующие имена DB/volumes.

```text
ssh -i <provided-identity> -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -p 40222 ivan@109.237.109.58 true
# Source inventory: stdin wrapper executes deployment/objects_inventory.py under installed /app Django runtime.
# PGOPTIONS: default_transaction_read_only=on, statement_timeout=60000, lock_timeout=5000, idle_in_transaction_session_timeout=60000.
# Source pg_dump command inside production db container, redirected to new protected local file:
pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB"
# Only in new isolated PostgreSQL:
pg_restore --exit-on-error --no-owner --no-acl -U objects_copy -d objects_copy
createdb -U objects_copy objects_original
pg_restore --exit-on-error --no-owner --no-acl -U objects_copy -d objects_original
# Exact checkpoint backend copied into inert isolated container using git archive + tar --strip-components=1:
git archive HEAD backend
```

Actual Python migration wrapper: MigrationExecutor → compare five plan entries with explicit allowlist → executor.migrate(targets) → call_command('migrate', interactive=False, verbosity=0) → table-fingerprint comparisons → check/migrate(check=True)/makemigrations(check=True,dry_run=True). Run only after baseline has been saved. Permissions/content types are created by post_migrate in the copy; DB ownership/ACL adaptation from --no-owner/--no-acl is environment preparation, not a production RBAC change.

Для повторения 32 API checks в isolated objects_copy: импортировать ObjectsTests, отсортировать его `test_` methods, для каждого создать instance, `with transaction.atomic(): case.setUp(); getattr(case,name)(); transaction.set_rollback(True)`. Использовать ALLOWED_HOSTS=testserver и guards по имени DB/container. Не запускать этот wrapper в source.

Browser command executed with private config (testDir points to worktree tests, outputDir outside Git, trace off, executablePath installed Edge, baseURL localhost:13031):

```text
AYS_OBJECTS_API_URL=http://localhost:18081
node frontend/node_modules/@playwright/test/cli.js test objects.spec.ts --config <private-playwright-config> --workers=1
```

Private artifacts/metadata находятся в защищённом каталоге вне Git. Raw data и dump в Git не включать. `backup.sh` с retention и restore scripts с DROP DATABASE не использовались. После проверок новые тестовые API/DB **остановлены**, volume/backup сохранены, local tunnel/UI закрыты. Production backend имеет прежние container ID/image и healthy status; исходный dump SHA повторно совпал. Копия не очищалась.

## Mapping, transfer и release

| Статус | Результат / основание |
|---|---|
| Code / synthetic acceptance | PASS; checkpoint runtime + окончательный browser-test diff проверен 6/6 |
| O0 актуальный snapshot | PASS для 09.10 source; все восемь целевых моделей пусты, grants и refs проверены с оговорённым scan coverage |
| Restored upgrade compatibility | PASS; five migrations, baseline preservation, checks, repeat plan и original restore |
| Legacy mapping | N/A — source Facility=0, Zone=0 |
| Репетиция переноса | N/A — переносить legacy нечего; backfill не выполнялся |
| Production release readiness | CONDITIONAL / NOT VERIFIED для полного выпуска; техническая DB совместимость PASS |
| Production deployment | NOT PERFORMED |

Нет неразрешённых реальных mapping/мультиюридических решений на этом snapshot. Это не blanket acceptance для будущих populated данных или другого источника. Перед выпуском остаются свежий maintenance DB/**media** backup, off-host checksum/restore, immutable release images и утверждённый actual migration plan; данный online DB snapshot не заменяет эти operational gates. Этот follow-up commit/push и обновление draft PR разрешены отдельным запросом на RC; новый production backup, merge и deployment в текущей задаче не выполняются.

## Release runbook — подготовлен, НЕ ИСПОЛНЕН

Runbook дополняет [PRODUCTION_DEPLOYMENT](PRODUCTION_DEPLOYMENT.md). Исполнение требует отдельного разрешения на maintenance/backup/smoke/deployment. В этой задаче нижеописанные production операции не запускались. Выход каждого этапа — закрытый gate с evidence; отсутствие evidence означает STOP, а не допущение.

### 1. Зафиксировать входные данные и проверить drift после snapshot

До окна согласовать оператора, exact RC SHA, backend/frontend image digests, защищённый server env path, release source directory, maintenance window, off-host destination и recovery owner. RC SHA получить из дочернего commit выше и заморозить; нельзя использовать mutable branch/tag как идентичность release. Серверный nongit source в /opt/ays-connect не перезаписывать checkout целиком.

Снять read-only container IDs/images/health, safe source hashes, PostgreSQL version, applied migrations и source inventory установленным source-compatible runtime с READ ONLY/REPEATABLE READ и прежними timeouts. Сравнить с source baseline main `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`, image `182f57f5…`, 101 applied и cutoff выше. Ожидаемые production Location/Facility/Zone после snapshot не предполагаются: проверить заново все восемь counts, refs и реальные grants. Изменение их данных снимает применимость empty-legacy N/A к новой копии и требует новой inventory/mapping review/upgrade acceptance до выпуска. Новые обычные Work/Projects записи сами по себе допустимы: проверить сохранность свежего baseline вместо требования 1950 строк навсегда.

Неизвестный source/image/migration drift, новые unsupported scopes/неоднозначные legacy refs или неподтверждённый target — STOP. Тот же O0 PASS исторического dump не переименовывать в PASS свежего состояния. Сверить runtime/schema RC с проверенным кодом; при их изменении определить новые gates, а не использовать прежние 585/32/6.

### 2. Собрать immutable images и закрыть пользовательские writers

До maintenance собрать release images из exact clean RC source без .env/dump/media; frontend VITE_API_URL=/api/v1. Создать проверенный image override для init/backend/всех шести workers с одним backend digest и frontend_assets с отдельным frontend digest; inspect подтвердить SHA и наличие каждого image. Новая конфигурация должна сохранять production volumes, iiko protected env wiring и ограничения Gunicorn. Не менять фактические runtime secrets. `config --quiet` обязателен, полный rendered config не выводить.

Параметры ниже — обязательные согласованные абсолютные пути/ID, не места, угаданные runbook. Команды выполняются оператором на Linux только после разрешения:

```bash
# Set AYS_RELEASE_ENV, AYS_RELEASE_ROOT, AYS_IMAGES_OVERRIDE out of band.
dc() {
  docker compose --env-file "$AYS_RELEASE_ENV" -p ays-connect-production \
    -f "$AYS_RELEASE_ROOT/docker-compose.prod.yml" \
    -f "$AYS_RELEASE_ROOT/docker-compose.iiko.yml" \
    -f "$AYS_IMAGES_OVERRIDE" "$@"
}
dc config --quiet
dc ps
```

Доказать maintenance ingress allowlist: доступ только оператору/согласованным smoke personas, остальные клиенты не могут писать. Если такого механизма нет, proxy остаётся остановленным до его настройки; простое обещание «не открывать writes» не является защитой. Зафиксировать IDs прежних containers/images и конфигурацию для resume/rollback. Затем закрыть traffic и остановить foreground/background writers с timeout, соответствующим iiko graceful timeout 300s:

```bash
dc stop -t 330 proxy backend recurrence_worker schedule_worker sla_worker \
  escalation_worker notification_worker performance_worker
# Pause periodic backup loop so retention cannot remove any prior backups.
dc stop -t 30 backup
dc ps
```

DB/Redis остаются running. Подтвердить завершение in-flight writes и отсутствие иных writers/cron/integration jobs. Пока это не доказано, backup/maintenance gate не закрыт. Записать начало write freeze UTC.

### 3. Свежий согласованный DB/media backup без retention

Согласовать новый уникальный BACKUP_ID; существующее имя означает STOP. PG dump и media брать в одном закрытом write window, сохранить ownership/ACL metadata для восстановления. Secret конфигурацию хранить отдельно штатно, не архивировать .env в Git. Не использовать backup.sh с retention либо restore scripts с DROP DATABASE.

```bash
# BACKUP_ID is agreed and matches ^[A-Za-z0-9_-]+$; no slash or traversal.
dc run --rm --no-deps --entrypoint sh -e BACKUP_ID="$BACKUP_ID" backup -ec '
  umask 077
  case "$BACKUP_ID" in ""|*[!A-Za-z0-9_-]*) exit 2;; esac
  destination="/backups/$BACKUP_ID"
  mkdir "$destination"
  pg_dump --format=custom --file="$destination/database.dump"
  tar -C /source -czf "$destination/media.tar.gz" media
  cd "$destination"
  sha256sum database.dump media.tar.gz > SHA256SUMS
  sha256sum -c SHA256SUMS
'
```

`mkdir` без -p защищает от перезаписи. Выйти при любой ошибке; записать source/application/migration version, время начала/окончания capture, filenames/bytes/SHA без содержимого. Backup не считается выполненным по одному сообщению shell или наличию старого файла.

### 4. Защищённая off-host копия и restore именно из неё

В согласованный новый каталог на другой машине вне Git/общих sync shares передать **database.dump, media.tar.gz, SHA256SUMS** по SSH. Доступ — только оператор/recovery owner, на Windows явный ACL; проверить место, шифрование/политику хранения и защищённый транспорт. При необходимости export из named volume делать через docker cp из остановленного backup container в новый private staging directory, не открывая permissions каталога всему миру. Не выводить пароль/DSN/ключ. Сверить каждый SHA на source и off-host; несовпадение — STOP.

Restore gate запускается **из off-host файлов**, не из server-local архива. Новые project/network/PG volume/DB/media volume, internal=true, без public ports/production credentials/networks/media и без workers/init/cron. Проверить tar member paths до распаковки; только относительные media/ paths без traversal и опасных link targets. Dump original immutable. Restore owner/ACL adaptation и тестовый signing secret протоколировать отдельно от schema/data изменений.

В новой пустой БД выполнить pg_restore --exit-on-error, проверить исходные constraints, baseline counts/UUID/code/types/FK, media hashes и referenced file availability, RBAC fingerprints. В ещё одной новой базе повторить original-version restore. Нельзя очищать существующую rehearsal DB/volume.

На свежей isolated upgraded copy проверить полный **фактический init command** из RC Compose, включая migrate, seed_permissions, collectstatic и подготовку прав файлов, без dependency traversal и без production mounts. Предыдущий PASS проверял migrations/post_migrate, не утверждает, что весь production init/seed_permissions уже репетирован. seed_permissions может согласованно обновить catalog labels; RolePermission/EmployeeRole и source user privileges должны остаться прежними. Объяснить все catalog/data deltas, повторить affected acceptance на свежих данных. Off-host DB+media restore и эта full-init rehearsal — отдельные незакрытые release gates.

### 5. Проверить точный migration plan и применить один раз

На свежей копии ожидаются ровно пять additions:

```text
access_control.0003_alter_rolepermission_scope
organizations.0004_location_address_location_business_status_and_more
organizations.0005_objects_guards_and_permissions
organizations.0006_responsibility_service_guard
organizations.0007_binding_lifecycle_guards
```

Сохранить ordered plan/hash и после него повторный empty plan. Если source изменился и delta другой — STOP, новый plan review/upgrade, не «догонять» production предположениями. Check/drift/RBAC/business data preservation и archive constraints должны пройти в копии до production migrate. Нельзя переписывать уже применённые migration files.

После закрытия gates 1–4 и отдельного разрешения оператора, при writers still stopped:

```bash
dc run --rm --no-deps init
```

Это единственный production migration/init invocation. Проверить вывод против approved plan; не повторять init вслепую при partial failure. Отдельно проверить migrate --check, grants fingerprints, zero unexpected classification/backfill и отсутствие unknown migrations. При unexpected data/privilege delta — STOP с write freeze.

### 6. Обновить сервисы, провести авторизованный smoke, открыть writes

```bash
dc run --rm --no-deps frontend_assets
dc up -d --no-deps --no-build --force-recreate backend
```

Backend и assets должны разрешаться к заранее проверенным immutable images; workers пока paused, proxy закрыт или под доказанным maintenance allowlist. Проверить backend health/ready, exact SHA/image, migration status, logs, старые consumers и файл-доступ. Не запускать frontend_assets повторно через dependency traversal.

Разрешение smoke должно явно назвать test accounts с нужными правами, маркированный объект, тип/timezone, maintenance route и допустимые write effects. Не создавать роль/аккаунт и не менять реальный пароль без такого разрешения. Для существующего scoped пользователя без глобальных прав согласовать доступный LegalEntity context; при пустом справочнике использовать согласованную global test persona, не создавать реальные LE/OrgUnit по предположениям.

Авторизованный UI/API smoke:

1. Через согласованный test-only ingress открыть UI exact RC assets. Создать ровно один `RELEASE-SMOKE-<RC_SHA>-<UTC>` объект типа office в preparation, timezone Asia/Novosibirsk. Сохранить payload/Idempotency-Key в закрытом журнале; повторить API с тем же ключом/телом — тот же UUID, второе создание/Audit/Outbox отсутствует. Другой payload с тем же ключом — 409.
2. Создать одну маркированную зону с текущей version; проверить parent UUID, наследованный контекст и рост version. Проверить list/detail/tree/lookups/counts и отсутствие лишних созданий. Без действующих согласованных LE/ответственного не переводить объект в operating.
3. Проверить view/manage/create и denied persona: недоступный объект detail 404, запрещённая операция 403, scoped counts/list/lookup не раскрывают hidden IDs. location.manage не подразумевает view, ответственному права автоматически не выдаются. Старый Location API write 405; Admin read-only. Проверить связанные People/Work/Requests/Projects без создания реальных задач/обращений вне разрешённого smoke.
4. Audit/Outbox entries относятся только к разрешённым действиям, повтор idempotency не дублирует событие. Workers ещё paused: никакой неразрешённой внешней доставки. Зарегистрировать разрешённые synthetic records; не удалять их прямым SQL. При согласованной уборке использовать domain close/archive после снятия blockers, сохраняя историю.

Проверка через SSH-only backend tunnel допустима до запуска proxy; локальные endpoints только loopback. Затем разрешённый maintenance ingress открывает proxy исключительно для smoke/оператора:

```bash
dc up -d --no-deps --no-build --force-recreate proxy
```

Проверить внешний HTTPS/certificate, live/ready, SPA load и authenticated read-only routes при закрытом доступе остальных пользователей. После успешного smoke запустить workers из того же backend digest:

```bash
dc up -d --no-deps --no-build --force-recreate recurrence_worker schedule_worker \
  sla_worker escalation_worker notification_worker performance_worker
```

С этого момента могут появиться **новые реальные background writes/доставки**, даже без публичного traffic. Зафиксировать время, проверить health/heartbeats, Outbox/failed/repeated events, real integration behavior и data invariants. Только после всех checks снять maintenance ingress restrictions, записать UTC открытия user writes. Возобновление periodic backup/retention — отдельное согласованное действие с сохранением pre-release restore point; не запускать retention автоматически сразу после release.

### 7. STOP и rollback с учётом новых записей

STOP: неизвестный production drift/новые legacy ambiguity, невалидный backup/checksum/media restore, unexpected plan, grant widening или business-data change, unhealthy service, scope leak/duplicate/cycle/archive bypass, неверный SHA/image/assets, failed/repeated Outbox, непредусмотренная внешняя отправка либо отсутствие доказанного write freeze/maintenance restriction. Оставить public ingress закрытым, остановить release writers, сохранить logs/evidence/current data.

- До любых migrations и переключения: возобновить именно прежние containers через docker start сохранённых IDs; не docker compose start с зависимостями. Backup failure не требует restore или seed. Проверить исходные image/migration/RBAC fingerprints и health, затем отдельно открыть traffic.
- После migrations, но **до новых реальных writes**, code-only rollback допустим лишь при проверенном schema compatibility window. По умолчанию считать его непроверенным. Восстановить fresh pre-release DB/media backup в **новые** DB/volumes, сравнить hashes/constraints/RBAC/прежние source values, согласованно переключить прежние images/config; изменённую DB/volumes сохранить для расследования. Не выполнять automatic reverse migrations, DROP либо перезапись действующей DB.
- Если единственные post-backup writes — заранее разрешённые synthetic smoke records/operational heartbeat/catalog changes, recovery owner должен явно разрешить их потерю после сохранения evidence; нельзя назвать такую БД «неизменённой». Учитывать Audit/Outbox и любые already delivered effects, которые restore не отменяет.
- После запуска workers/доставок или открытия пользовательских writes презумпция **новых реальных данных**: запрет blind restore старого backup. Закрыть ingress/остановить writers, сделать отдельную защищённую аварийную копию текущей DB/media по разрешению, определить полный delta и сохранение/replay новых данных либо forward fix. Переключение/restore только после решения recovery owner о сохранности данных и согласованной компенсации необратимых внешних действий.

### Остаточные условия выпуска

1. Отдельное разрешение release/maintenance/write smoke, immutable RC images и работающий test-only maintenance ingress.
2. Fresh production drift/inventory/grants review после snapshot; при изменениях — обновлённый data/upgrade gate.
3. Согласованный свежий DB/media backup, source/off-host SHA match, защищённая off-host копия и independent DB/media restore из неё.
4. Fresh-copy rehearsal **точного production init**, approved five-entry plan либо отдельно reviewed новая delta; unchanged real grants/business data.
5. Авторизованный create/replay/zone/rights smoke, HTTPS/consumers/workers/Outbox acceptance и утверждённый recovery plan для новых записей.

До закрытия этих условий **production readiness CONDITIONAL**, deployment **NOT PERFORMED**. Подготовка/публикация RC не закрывает их автоматически.
