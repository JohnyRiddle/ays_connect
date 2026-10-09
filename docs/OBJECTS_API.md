# Объекты — API локального кандидата

Prefix: `/api/internal/v1/objects/`, Bearer authentication. Location UUID остаётся идентичностью. Доступ и область видимости: [архитектура](OBJECTS_ARCHITECTURE.md). Production acceptance заблокирован [O0](OBJECTS_O0_ACCEPTANCE.md).

| Метод / путь | Назначение |
|---|---|
| GET / | Реестр объектов, SQL visibility, серверная пагинация |
| POST / | Создать объект; обязательный Idempotency-Key |
| GET /{uuid}/ | Карточка объекта или зоны |
| PATCH /{uuid}/ | Редактирование с version |
| POST /{uuid}/lifecycle/ | operate/seasonal_close/close/reopen/archive/restore |
| POST /{uuid}/responsible/ | role=manager/technical, employee UUID или null для завершения |
| GET, POST /{uuid}/zones/ | Пагинация дочерних зон / создать зону |
| POST /{uuid}/move/ | parent UUID или null; optimistic version |
| GET /{uuid}/responsibilities/ | Разрешённые People policy периоды ответственности |
| GET /{uuid}/history/ | Пагинация безопасной истории Audit |
| GET /{uuid}/related/?kind=… | people/tasks/requests/projects/participating_projects |
| GET /capabilities/ | can_create и business_types |
| GET /lookups/ | Видимые parent, LegalEntity, OrgUnit, active Employee |
| GET /tree/ | Видимые узлы с пагинацией |
| GET /move-targets/?source={uuid} | Видимые разрешённые родители, pagination/search |

POST обязательные поля: name (200), business_type, timezone (64). Типы: restaurant/bar/nightclub/hotel/dormitory/warehouse/production/office/technical/other. Optional: parent, address (500), legal_entity, org_unit, contacts (1000), work_schedule (1000), description (10000), manager, technical, confirm_duplicate. IDs — UUID, nullable необязательные связи. Неизвестные поля, client UUID/code/version/archive/actor запрещены. IANA timezone валидируется сервером.

```json
{"name":"Синтетический офис","business_type":"office","timezone":"Asia/Novosibirsk","address":"Синтетическое местоположение"}
```

Вероятный дубль — видимое нормализованное имя в том же parent-контексте. Продолжение требует `confirm_duplicate=true`; уникальности по имени нет. Idempotency-Key длиной до 128 привязан к actor/operation. Тот же payload возвращает тот же объект (200); первый create — 201; изменение payload — 409. Конкурентный replay не повторяет Audit/Outbox; доступ проверяется заново.

PATCH обязательный version≥1; допустимы name/business_type/timezone/address/org_unit/contacts/work_schedule/description. У зоны — только name/description. Parent и LegalEntity не меняются PATCH. Все POST mutations требуют version текущего узла; создание зоны увеличивает version родителя. Lifecycle принимает action и reason≤500; закрытие, сезонные изменения и reopen требуют причину. Responsible принимает role и employee; zone POST — name/description; move — parent.

Карточка содержит id/code/name/node_kind/business_type/business_status/parent/address/timezone/legal_entity/org_unit/contacts/work_schedule/description/is_archived/version/created_at/updated_at, видимые имена связанных сущностей, available_actions. Недоступные связные IDs/имена не отдаются.

Фильтры реестра: search (имя/код/адрес), business_type, business_status, archived=false/true/all (default false), legal_entity, parent, geography (видимый geography/site и поддерево), responsible (видимый Employee с текущей ответственностью), page. Неверные UUID/enum — 400. Pagination: count/next/previous/results. Count уже ограничен политикой; related kinds включают объект и вложенные зоны.

Права: location.view и location.create/edit/manage_zones/assign_responsible/change_status/archive/restore/move. location.manage разрешает только явный mutation allowlist, view отдельно. Создание требует global либо явного LegalEntity scope, а также видимости результата. Initial responsible дополнительно требует assign_responsible и People visibility. Scope location не разрешает создание соседнего объекта.

400 — поля/состояние/блокеры; 403 — право операции; 404 — отсутствующий/невидимый объект или relation; 409 — version/idempotency conflict; 500 — безопасное общее сообщение без SQL/internal exception. Ошибки используют общий error envelope code/message/details. Реестр Objects не возвращает unclassified старые Location, но существующий read-only `/locations/` сохраняет scoped доступ к ним.

Lookups сотрудников сейчас ограничены первыми 200 видимыми active Employee; UI move показывает первую страницу кандидатов (API поддерживает search/page). Для больших каталогов нужен отдельный UX поиска, не полный client-side список рабочих записей.

Review 08.10.2026: capabilities.can_create использует пересечение create/view contexts, location.manage не означает view. Restore под архивным/неактивным предком — 400. Старый read-only locations API также маскирует невидимые relation IDs. Реальные mapping/перенос/production readiness — NOT VERIFIED.
