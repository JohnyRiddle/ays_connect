# Объекты — контракт первой версии и граница O0

02.10.2026. Каноническая идентичность — существующий Location UUID. Новая разработка разрешена уточнением пользователя на изолированной PostgreSQL с синтетическими данными и обратно совместимыми добавлениями схемы. Перенос/классификация существующих записей и production readiness заблокированы до актуальной инвентаризации: [O0 DATA BLOCKED](OBJECTS_O0_ACCEPTANCE.md).

Старые UUID и непустые code/FK сохраняются; location_type не переписывается. Unclassified явно отделён от новых object/zone. Основное юрлицо — текущий одиночный FK; реальные мультиюридические исключения не преобразуются предположениями.

Первая версия доступа: global; legal_entity с явным EmployeeRole.legal_entity; location с явным EmployeeRole.location только на объект и вложенные зоны. Geography grants и NULL/own/team/participating/org_unit fail closed. location.manage — восемь явных mutations без view; новые RolePermission каталожные записи автоматически никому не выдаются.

O0 PASS требует подтверждённого snapshot/provenance, read-only inventory, semantic review неструктурированных ссылок, подготовки кандидатов Facility→Location/CREATE_NEW, затем Zone и разрешения неоднозначностей. Mapping минимум: source_model/source_id/target_location_uuid либо CREATE_NEW/basis/confirmation/conflicts/dependent_records. Private JSON вне Git. Одного имени недостаточно; UNRESOLVED не означает CREATE_NEW. Объединение источников — отдельное предметное решение.

Пустые локальные БД доказывают N/A mapping только этих snapshots. Синтетический upgrade доказывает техническую сохранность созданных fixtures, не совместимость актуальной рабочей БД. Реализация: [архитектура](OBJECTS_ARCHITECTURE.md), [API](OBJECTS_API.md), [acceptance](OBJECTS_ACCEPTANCE.md).
