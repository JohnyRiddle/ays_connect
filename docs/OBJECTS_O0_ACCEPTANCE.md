# Объекты — O0

## 09.10.2026 — O0 inventory PASS, рабочий источник доступен

Предоставленный пользователем SSH identity дал доступ к документированному работающему `ays-connect-production`. **DATA BLOCKED снят для snapshot 09.10.2026.** Источник — установленный backend `/app`, его PostgreSQL `db/ays_connect`, 17.11; schema preflight восьми моделей PASS; REPEATABLE READ / READ ONLY, statement_timeout 60s, lock_timeout 5s, idle timeout 60s. Source migrations 101/0/0; 407/407 нормализованных Python/requirements runtime files совпали с main `64f85fa…`, immutable image зафиксирован в readiness report. Health marker не использован как единственное доказательство.

| Актуальный источник 09.10 | Location | Facility | Zone | Company | Region | Cluster | LegalEntity | OrgUnit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PostgreSQL работающего ays-connect-production backend | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

71 FK field, все целевые ссылки=0, errors=0. Дубли/циклы/orphans/активные потомки/unknown types/мультиюридические и zone/root исключения N/A: целевых записей нет. Один global grant location.view и один global location.manage, одна EmployeeRole; в копии новая test persona с 125 grants действующей роли прошла capabilities/create/replay. Реальные аккаунты/роли не менялись. Mapping и репетиция переноса **N/A для этого подтверждённого рабочего snapshot**, Facility/Zone отсутствуют. Искусственного реального legacy не создавалось.

Fresh DB dump: получение завершено 2026-10-09T06:53:54.581111+00:00 (точное время открытия PostgreSQL snapshot не записано), SHA `041c5fc9f2e6b7dd14b4c78909d50dd27afb6ff8d0e0f0a54126444816c3521b`, хранится с ограниченным ACL вне Git/OneDrive. Исходная restore-копия: 196 tables/1950 rows. Semantic scan 505 полей/5477 непустых значений: явные object keys/ID patterns=0, audit object refs=0, GFK fields=0; произвольные encoded/name-only ссылки автоматикой не исключаются. ПДн/значения не опубликованы.

Upgrade рабочей копии **PASS**: ровно access_control 0003 + organizations 0004..0007; 192 old tables неизменны, допустимые catalog/migration delta перечислены отдельно; RolePermission/EmployeeRole совпали. Check/drift/repeat plan PASS. Независимый original restore совпал со всеми 196/1950 fingerprints. API 32/32 внутри atomic rollback; browser окончательного test diff 6/6, 29.9s. Исходные 2 Work/1 Project сохранены и доступны маркированному test-admin; после тестов допустимо изменились только три number-counter rows от тестовых созданий. Runtime/schema не изменялись; в локальном browser test добавлены две URL waits, прежний checkpoint не включает этот follow-up.

**Production readiness — CONDITIONAL / NOT VERIFIED полного выпуска; deployment — NOT PERFORMED.** Свежий online DB snapshot не заменяет maintenance DB/media/off-host restore gate. [Точные версии, commands, ограничения и план выпуска](OBJECTS_RELEASE_READINESS.md). Старая таблица локальных нулей ниже — историческое evidence, не основание текущего рабочего N/A. Предыдущие отказы SSH также исторические. Documentation/browser-test follow-up публикуется отдельно по явному запросу на RC; новый production backup, merge/deployment не выполняются.

## История: повторная проверка 09.10 до предоставления identity

**O0 DATA BLOCKED. Реальные mapping, перенос и production readiness — NOT VERIFIED.** Проверен опубликованный checkpoint `73a8092b4b0675daf2f0a6ab11fb8e090226f58c`, draft PR #1 на main `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`; все 36 source SHA-256 совпали с manifest. Код не менялся, synthetic acceptance 585/36/8/6 остаётся PASS по gate 08.10.

Документированный production `/opt/ays-connect`, проект `ays-connect-production`, `109.237.109.58:40222` повторно недоступен: SSH BatchMode/StrictHostKeyChecking с default identities и отдельно существующим deploy-key завершились `Permission denied (publickey)`, exit 1. Ключи и env не печатались. Backup `/home/ivan/ays-iiko-backup-20260910` исторический; его текущая актуальность, checksum, PostgreSQL/application version и applied migrations не подтверждены. Production counts ниже по-прежнему НЕ ПРОВЕРЕНЫ.

Локальный Docker API вернул 500; новые snapshots не снимались, старые counts не обновлялись. Локальные 0/0/0 — evidence только от 02.10, не состояние production на 09.10. Upgrade рабочей копии, семантический JSON/string/GFK scan, реальные grants, активные LegalEntity, zone/root mismatch и lookup на реальном объёме не выполнены. Mapping не предполагался; перенос BLOCKED, не N/A. Новый [release readiness report](OBJECTS_RELEASE_READINESS.md) фиксирует все статусы, ограничения инструмента, timeouts и безопасный порядок новой isolated restore без удаления существующих БД.

Следующий необходимый шаг: настроить разрешённый SSH-доступ существующим deploy-key к документированному серверу и подтвердить актуальность `/opt/ays-connect`. Секреты в чат не нужны; подготовка кандидатов входит в дальнейшую инвентаризацию. В этой задаче commit/push/merge/deployment и изменения production не выполнялись. Checkpoint ранее опубликован по отдельному запросу; следующие разделы — историческое evidence 02.10.

## Evidence 02.10.2026

**O0 DATA BLOCKED.** Актуальная рабочая БД и её восстановленная копия не подтверждены. Это блокирует перенос реальных данных, классификацию старых Location и production readiness. Согласно уточнению пользователя разработка O1/O3/O4 и обратно совместимая схема продолжены на отдельной PostgreSQL с синтетическими данными. O0 PASS не заявляется.

## Checkout и контуры

Исходный checkout: main, `e03731c9860ad025bfa6a4889f8b9857e367cfc7`; незакоммиченные Cards/assets/CURRENT_STATE сохранены. После fetch использована актуальная origin/main `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`. Реализация находится в `C:/Users/riddl/.codex/worktrees/objects/AYS Connect`, ветка `codex/objects`. Исходный checkout оставлен на main. Reset/clean, commit/push/merge и production deployment не выполнялись.

По [IIKO_DEPLOYMENT](IIKO_DEPLOYMENT.md) и [INTEGRATED_RELEASE_2026_09_27](INTEGRATED_RELEASE_2026_09_27.md) рабочий контур — `ays-connect-production`, сервер `109.237.109.58:40222`, каталог `/opt/ays-connect`. Последняя документированная основа — non-Git deployment `98c23a7+backup-hotfix` с iiko/Cards; это не подтверждение его состояния на 02.10.2026. Read-only попытка SSH с BatchMode/StrictHostKeyChecking закончилась `Permission denied (publickey)`, инвентаризация не началась. Не искались новые credentials и не запрашивались секреты. Документированный старый backup не объявлен актуальной восстановленной копией.

| Проверенный контур | Location | Facility | Zone | География / LegalEntity / OrgUnit | FK-поля | JSON/text/string discovery | applied / pending / unknown migrations |
|---|---:|---:|---:|---|---:|---:|---|
| ays-projects-acceptance-backend-1, локальный | 0 | 0 | 0 | все 0 | 71 | 505 | 101 / 0 / 0 |
| ays-connect-pilot-backend-1, локальный | 0 | 0 | 0 | все 0 | 60 | 412 | 79 / 0 / 5 |
| Документированный production, доступа нет | НЕ ПРОВЕРЕНО | НЕ ПРОВЕРЕНО | НЕ ПРОВЕРЕНО | НЕ ПРОВЕРЕНО | — | — | — |

Локальные контейнеры используют собственные установленные Django-код и DB settings. DSN и секреты не выводились. Нулевые локальные записи не доказывают отсутствие production-данных. `unknown` означает applied migrations, не найденные в установленном коде pilot; их происхождение требует отдельного разбора. Созданный позже синтетический `ays-objects-db` — контур разработки, а не доказательство O0; его меняющиеся browser fixtures не включены в эту таблицу.

## Read-only инструмент и mapping

`deployment/objects_inventory.py` выполняет отдельную PostgreSQL транзакцию REPEATABLE READ / READ ONLY, проверяет `transaction_read_only=on`, всегда откатывает её. Код 0 означает успешное чтение, а не O0 PASS. В локальные контейнеры копировался только скрипт в `/tmp`; migrate/seed/bootstrap и исправлений в этих БД не было.

Инвентаризируются Location/Facility/Zone, Company/Region/Cluster, LegalEntity/OrgUnit, пустые поля/контексты, распределения типов/активности, кандидаты дублей, циклы, отсутствующие родители, миграции и все зарегистрированные FK/OneToOne. Число зависимостей — ссылки по полям, не уникальные бизнес-записи. Кандидаты нескольких юрлиц включают исторические FK и не доказывают несколько **действующих** юрлиц.

stdout содержит агрегаты без названий/ID/произвольных типов. `--private-output` пишет JSON только по абсолютному пути вне репозитория, запрещает перезапись. Содержит source model/ID/context, кандидатов target UUID, basis, confirmation, conflicts и dependent_records. Facility-кандидаты требуют совпадающего непустого стабильного кода либо нормализованного имени **вместе с непустым совпадающим адресом**. Одного имени недостаточно. Zone ожидает подтверждения Facility. Кандидаты не применяются автоматически; неоднозначные соответствия и объединения выносятся владельцу данных. Готовый mapping до инвентаризации не требуется: его подготовка входит в O0.

Mapping **N/A только для двух проверенных пустых локальных snapshots**: Facility=0 и Zone=0. Для production статус UNKNOWN/DATA BLOCKED. Искусственные legacy-записи для O0 не создавались. Legacy-записи в отдельном upgrade fixture маркированы синтетическими и проверяют сохранность FK.

JSON/text/string/GFK — discovery полей, а не semantic scan значений. Отсутствие таких ссылок не доказано; review выполняется на подтверждённой актуальной копии без публикации ПДн. Частные выгрузки и рабочие данные в Git отсутствуют.

## Что остаётся для закрытия O0

1. Подтвердить актуальный контур/копию, provenance, дату, охват и соответствующий код; выполнить read-only inventory.
2. На её основе подготовить Facility-кандидатов, затем Zone; вынести только неоднозначные решения. Сохранить UUID/коды, не трактовать UNRESOLVED как CREATE_NEW.
3. Проверить неструктурированные ссылки и периоды действующих OrgUnit/LegalEntity/EmployeeAssignment; решить реальные мультиюридические исключения.
4. Разобрать migration drift pilot и реальные grants/географические исключения. Неподдержанный географический scope пока fail closed.
5. Только после подтверждения данных проектировать явный dry-run/repeat/conflict log и перенос. Сейчас преобразования данных отсутствуют.

## Evidence

Инструмент: **8/8** unittest в Docker с network none; read-only snapshots двух локальных PostgreSQL; 1500-узловой цикл, privacy stdout, запрет name-only mapping и приватной выгрузки внутрь Git покрыты тестами. Реализация и синтетические gates: [OBJECTS_ACCEPTANCE](OBJECTS_ACCEPTANCE.md).

```text
python -m unittest discover -s deployment -p test_objects_inventory.py -v
python deployment/objects_inventory.py --private-output <absolute-private-path-outside-repository>
```

Вторую команду запускать средствами **соответствующего копии Django runtime**. Обычный Compose startup с migrate/seed для аудита рабочей базы запрещён.
