# Phase 1.3A — Business Calendars / SLA Policies

Дата реализации: 27.08.2026.

## Результат

В отдельном приложении `backend/sla` реализовано конфигурационное ядро SLA:

- бизнес-календари с IANA timezone, недельным расписанием, исключениями и несколькими интервалами в день;
- immutable-снимки опубликованных версий календарей;
- timezone-aware расчёт рабочего времени, включая выходные, праздники, разрывы расписания и DST;
- черновики SLA-политик и immutable опубликованные версии;
- response/resolution нормативы, elapsed/business time, пороги предупреждений и политика пауз;
- правила назначения и детерминированный resolver по специфичности и `order`;
- preview API для выбора политики и расчёта срока;
- permissions, Django Admin, Audit и transactional Outbox.

Runtime-экземпляры SLA, эскалации и изменение lifecycle заявок в эту фазу не входят.

## API

Ресурсы доступны под `/api/internal/v1/`:

- `sla/calendars/` — CRUD, интервалы, исключения, publish/deactivate;
- `sla/policies/` — draft CRUD, publish/deactivate;
- `sla/assignment-rules/` — CRUD/deactivate;
- `sla/policy-preview/` — подбор опубликованной версии;
- `sla/deadline-preview/` — расчёт срока без изменения заявки.

## Quality gate

PostgreSQL 17.11 gate пройден: миграции применены на чистой БД и upgrade-копии с сохранением контрольных данных; полный backend suite — 129/129, SLA domain — 8/8. Исправлена обнаруженная PostgreSQL-specific ошибка блокировки nullable outer join при publish политики.
