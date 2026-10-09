# Объекты — аудит и исполнение

База `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`, ветка `codex/objects`, отдельный managed worktree. Исходные грязные файлы сохранены. Перед работой прочитаны AGENTS/README/CURRENT_STATE/PROJECT/ARCHITECTURE/DECISIONS и профильная документация.

## Исходные выводы и изменения

Location уже был физическим UUID для People/Work/Requests/Projects/SLA/Performance/EmployeeRole. OrgUnit — организационный контекст, Project уже имеет одиночную Location; они сохранены. Facility/Zone использовались legacy tasks/checklists/sensors/knowledge/learning: удаления или массового переноса нет. iiko slug не является доказанным mapping.

Исходные общий Location ModelViewSet, unscoped list и writable Admin были обходами будущего сервиса. Они заменены read-only scoped API/Admin. Objects реализован специализированными командами над Location, не новым справочником. Scope location добавлен в общий enum без расширения сторонних policies; новые guards защищают managed UUID и архивные FK bindings.

## Выполненные этапы и оставшееся

| Этап | Результат | Граница |
|---|---|---|
| O0 | read-only инструмент 8/8, два локальных inventory, contract | DATA BLOCKED: рабочая БД неизвестна/SSH недоступен; production counts неизвестны |
| O1 | core/API/create/idempotency/lifecycle/permissions/Audit/Outbox | Проверено только synthetic PostgreSQL |
| O2 schema | append-only install/upgrade/repeat/restore, legacy UUID/FK preservation | Synthetic PASS; реальный mapping/dry-run/backfill/conflicts BLOCKED |
| O3 | registry/create/detail/zones/responsibles/history, URL filters/mobile/errors | Browser gate и build; ограничения больших lookup каталогов документированы |
| O4 | People/Work/Requests/Projects lazy policy-scoped relations, prefill | Synthetic API/browser и общий regression; production semantics не доказаны |
| O5 local | свежие PostgreSQL regression, concurrency/security, build/browser, docs | Локальный checkpoint candidate, не production release acceptance |

Дальше требуется актуальная read-only инвентаризация, а не готовый mapping от пользователя. После неё подготовить кандидатов, подтвердить неоднозначные соответствия, мультиюридические исключения и реальные права; только затем проектировать data-transfer dry-run/repeat/conflict log. Commit/push/merge/deployment остаются отдельным явным запросом. Evidence: [OBJECTS_ACCEPTANCE](OBJECTS_ACCEPTANCE.md).
