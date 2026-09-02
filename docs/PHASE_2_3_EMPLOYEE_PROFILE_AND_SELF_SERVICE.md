# Phase 2.3 — Employee Profile & Self-Service

Статус: COMPLETE. PostgreSQL Quality Gate PASS 02.09.2026.

## Архитектура

`Employee` остаётся единственным кадровым объектом и владельцем avatar. `EmployeeProfile` — OneToOne-расширение только для self-service данных, типизированной видимости и optimistic version. Кадровые изменения проходят через отдельный `EmployeeDataChangeRequest`: Service Request Core не используется как HR/BPM-механизм. Organization, Teams, RBAC, Audit, transactional Outbox и Notification Core не дублируются.

## API

Канонический namespace: `/api/internal/v1/people/`. Реализованы `me`, completeness, organization, teams, visibility, avatar, self/admin change requests и privacy-aware directory. Avatar выдаётся только через защищённый endpoint; прямой public media URL не является контрактом.

## Безопасность

Self-service использует связанного активного Employee. Кадровые поля защищены allowlist, optimistic locking, запретом self-approval и stale-snapshot проверкой. Audit/Outbox содержат только идентификаторы и названия изменённых полей. Avatar: лимит 5 MB, JPEG/PNG/WebP определяется по содержимому, SVG запрещён, имя генерируется сервером, удаление предыдущего файла выполняется после commit.

## Permissions

Добавлены все `people.profile.*`, `people.directory.*` и `people.change_request.*` коды из Phase 2.3 в seed-команду и append-only migration `employees.0012`.

## Quality Gate

- PostgreSQL 17.11 (изолированный baseline-контур): clean migrations PASS;
- upgrade rehearsal `employees.0010 → 0011 → 0012`: PASS;
- Phase 2.3: 27/27 PASS, включая 10/10 PostgreSQL concurrency и security/IDOR;
- полный backend regression: 326/326 PASS, skipped 0;
- frontend production build: PASS;
- `manage.py check`, migration drift и `git diff --check`: PASS.
