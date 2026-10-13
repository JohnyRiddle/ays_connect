# Подготовка импорта справочника ЦФО

Обновление: последующее поручение «Приступай» выполнено в рабочей базе.
[Результат применения и проверки](CFO_IMPORT_ACCEPTANCE.md). Ниже — история подготовки.

13.10.2026. Подготовка пакета согласована пользователем сообщением «Согласовано».
Согласование относится к подготовке и её отдельному commit; production apply
не выполняется, незаполненные UUID/обязательные поля не считаются подтверждёнными.
Подготовлен пакет в защищённом каталоге
`I:\AYS Connect\TaskPatch\CFO-import-20261013`. Данные не применялись.
Исходный workbook и существующие dirty-файлы других checkout сохранены.

Из 60 исходных строк 55 включены: 50 предложенных объектов Location,
2 организационные единицы OrgUnit и 3 организационные службы OrgUnit.
Пять исключений пользователя сохранены как отдельные записи, не как удаления.
54 связи относятся к 21 предлагаемому LegalEntity; один null подтверждён
пользователем. Raw названия/юрлица/группы и номера строк сохраняются в плане.

Формат `ays-connect-cfo-import-plan/1` является проектом сопоставления, не
Django fixture и не HTTP payload. Ledger требует подтверждённых UUID и payload
checksum, actor/operation, version и результатов Audit/Outbox. Object API использует
actor-bound Idempotency-Key; LegalEntity/OrgUnit codes предлагаются в отдельном
пространстве импорта с проверкой идентичности. Ни одно имя не означает автоматического
слияния с существующей сущностью или выдачи grants.

Физические объекты создаются только через production ObjectService/API;
не через legacy Location CRUD. Parent object допускает зоны, не другие objects;
зоны наследуют юрлицо родителя. ГК финансового справочника не превращаются
автоматически в географию/площадки/организационное дерево. Типы бизнеса и timezone
подлежат проверке, кроме точечных пользовательских уточнений.
Организационные службы используют OrgUnit department с metadata kind service,
управляющая компания — OrgUnit company. Новые ServiceType каталога Requests не нужны.

Применение требует существующих Permission/Audit/Outbox. OrgUnitService уже
содержит audit/event hooks; текущий LegalEntity CRUD собственного hook не имеет,
поэтому массовая запись юрлиц требует отдельного аудируемого административного
процесса. Модель LegalEntity не содержит ИНН: реквизиты в review workbook служат
для сверки, не являются поддержанными полями API.

Read-only production inventory: LegalEntity 0, OrgUnit 0, Location 5.
Запрошенные руководители в People по предоставленным именам не найдены;
names сохранены как намерение, UUID/позиции не выдуманы. Новые employees,
account/position assignments, object grants или departments старых задач не создавались.
Для задач нужен активный manager_position и единственный активный сотрудник
внутри OrgUnit; строка ФИО или manager_employee не заменяет этот контракт.

Проверено: 60 исходных строк сверены с saved review workbook, 55+5 reconciliation,
уникальные source keys, 54/21 FK-ссылки, target enum/model compatibility,
пользовательские исключения и типы, formula summary 55/50/2/3, визуальный просмотр
обоих листов, ZIP CRC/SHA и EFS файлов — PASS. Backend runtime не менялся;
новые миграции и полный повтор backend тестов не требуются для подготовки данных.

Пакет содержит review workbook, JSON, read-only validator, README и manifest.
Raw бизнес-данные и private inventory в Git не добавлены. `ready_for_apply=false`:
до записи согласовать типы/географию/идентификацию юрлиц, Employees/позиции,
подтвердить существующие UUID, выполнить rehearsal и получить разрешение production apply.
