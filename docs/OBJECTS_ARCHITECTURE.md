# Объекты — архитектура локального кандидата

02.10.2026: O1/O3/O4 реализованы и проверены на синтетической PostgreSQL; [O0 DATA BLOCKED](OBJECTS_O0_ACCEPTANCE.md). Каноническая идентичность — существующий `organizations.Location.id` (UUID), нового object_id и отдельного физического справочника нет.

## Схема и дерево

Location дополнен `node_kind` (unclassified/geography/site/object/zone), отдельными business_type/business_status, адресом, timezone, OrgUnit, контактами, графиком, описанием, архивом и version. Новые объекты стартуют preparation/version=1, получают неизменяемый OBJ-код из PostgreSQL sequence с существующим unique constraint. Пропуски допустимы, занятые старые коды пропускаются.

Старые UUID/code/location_type/FK не переписаны; существующие строки становятся unclassified, business_status/timezone пусты. Это **отсутствие классификации**, а не присвоение рабочего статуса. Geography/site нельзя создать через публичную форму Objects; импорт/классификация реальной географии ждёт O0. Допустимы geography→geography/site/object, site→object, object→zone, zone→zone. Корневой объект допустим; корневая зона запрещена. Зоны наследуют контекст своего объекта. Юрлицо географического родителя объекту автоматически не присваивается.

Основное LegalEntity — существующий одиночный FK. OrgUnit должен быть действующим и согласованным с явно выбранным LegalEntity. Автоматических OrgUnit/Facility/зон/ролей нет. PATCH не меняет LegalEntity или parent: move — отдельная команда. Реальная модель мультиюридических исключений остаётся нерешённой до инвентаризации.

## Транзакции и защита

`object_services.py`: явные allowlists, валидация IANA timezone/полей/связей, повторная проверка scopes, optimistic version. Location, ответственность, Audit, transactional Outbox и idempotency result сохраняются атомарно. Replay проверяет актуальные права; actor+operation+key и payload hash исключают повторное создание/событие, другой payload даёт 409.

Все записи дерева и проверки новых привязок сериализуются PostgreSQL advisory transaction lock. Родители перечитываются после lock; цепочки проверяются на циклы. Employee row locks берутся до object lock в назначении и увольнении. DB guards запрещают обход ORM для managed Location, изменение code/kind, физическое удаление, неверный parent, циклы и запись ответственности вне сервисного контекста. Transaction-local capability сбрасывается, включая пойманные ошибки/savepoint rollback. Это защита прикладных путей; владелец БД не является недоверенным клиентом.

Триггеры Location FK не допускают новые/реактивированные привязки к архивному узлу или архивному предку. Существующие исторические связи допускают обновление без изменения привязки. PerformanceFact исключён как воспроизводимая историческая проекция. Unclassified старые inactive Location не переклассифицируются DB guard. Consumer hooks действуют в Employees/Assignment/Teams, Work/Template, Requests/schema LOCATION и Projects; policies этих доменов сохранены.

## Ответственность и lifecycle

`LocationResponsibility`: Employee, manager/technical, valid_from/to, причина завершения; partial unique — одна открытая запись на роль/объект. Смена закрывает период и создаёт новый. Termination/deactivate закрывают текущую ответственность, увеличивают version и пишут Audit/Outbox; реактивация ничего не восстанавливает. Состав сотрудников берётся из действующих EmployeeAssignment с периодами, фильтруется People policy.

Preparation→operating требует адреса/описания местоположения, LegalEntity и активного управляющего. Operating↔seasonal_closed фиксирует причину/время и не меняет People/Work. Close с причиной доступен из неокончательного статуса; reopen с причиной возвращает preparation. Архив отделён от business_status: объект должен быть final_closed, не иметь активных дочерних узлов/назначений/ответственности/незавершённых Work-задач. Ответ о блокере не раскрывает скрытые связи. Restore сохраняет final_closed, UUID, историю, не восстанавливает назначения. Зона может архивироваться независимо при тех же блокерах.

Move проверяет права source/target, version, типы и цикл. Cross-object move зоны с любой существующей FK-ссылкой запрещён; для свободного поддерева обновляется контекст LegalEntity/version. Физического delete API нет.

## Доступ и связанные домены

`LocationAccessPolicy`: global; legal_entity с явным контекстом; location только на объект и вложенные зоны. Geography grants, NULL/own/team/participating/org_unit fail closed. location.manage — явная совместимость восьми mutations, **не** location.view. Назначение управляющим не выдаёт прав. В общий PermissionService добавлен scope без расширения Work/Projects.

Visibility применяется к SQL queryset до pagination/search/tree/lookups/counts. Недоступные связанные IDs и имена маскируются, история отдаёт безопасный allowlist. `/locations/` теперь read-only и scoped; Location Admin read-only со scoped queryset. Detail и mutations требуют view плюс право операции.

Related endpoint лениво использует People/Task/ServiceRequest/Project policies; count и list берутся из одного queryset. Прямые проекты отличаются от участия через доступные задачи, недоступный Project не раскрывается. Предзаполнение Work/Request Location использует существующие формы и повторную серверную проверку.

## Миграции и предел совместимости

Append-only: access_control 0003; organizations 0004 (добавления), 0005 (sequence/guards/permission catalog без выдачи ролей), 0006 (responsibility guard), 0007 (reactivation guard/historical PerformanceFact). Старые миграции не изменены; Facility/Zone и их consumers сохранены. Обратный schema rollback не является планом production rollback: при выпуске нужен подтверждённый restore point.

Clean install, синтетический baseline upgrade, repeat plan и pg_dump/restore проверены. Совместимость актуальной рабочей БД, её свободных типов, grants и внешних/неструктурированных ссылок **не проверена**. Массового mapping/backfill нет.

Финальное review 08.10.2026: create требует совместимых create/view contexts; domain writes требуют view+operation; inactive User denied. Старый Location serializer и Admin не раскрывают невидимые FK. Restore проверяет всю цепочку предков до записи. UI PATCH включает только изменённые поля, сохраняя скрытые связи и чужие неизменённые поля после version refresh. [Gate/manifest](OBJECTS_CHECKPOINT.md).

09.10.2026 проверен подтверждённый рабочий snapshot: все восемь целевых моделей пусты; O0 inventory и upgrade его изолированной копии PASS, Facility/Zone mapping и перенос N/A. Реальные непустые Location/мультиюридические исключения отсутствуют в snapshot и не объявляются проверенными сценариями. Сохранность текущих Work/Projects и grants подтверждена; DB/media release readiness остаётся отдельным gate. Правила архитектуры и runtime/migrations не менялись; follow-up меняет только две browser URL waits и documentation. [Readiness](OBJECTS_RELEASE_READINESS.md).
