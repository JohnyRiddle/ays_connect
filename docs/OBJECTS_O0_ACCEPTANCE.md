# Объекты — O0, 02.10.2026

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
