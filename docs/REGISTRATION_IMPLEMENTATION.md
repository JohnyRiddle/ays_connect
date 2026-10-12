# Регистрация и объектные назначения — 12.10.2026

База main `5d9da353ee552af3b0c2182c374f132d0e91e2ce`, ветка `codex/registration`.
Production не изменяется; интеграция iikoCard — отдельный этап.

## Проверенные механизмы и реализация

Переиспользуются User, Employee, RegistrationRequest, EmployeeInvitation,
EmployeeService, EmployeeAssignmentService, Role/EmployeeRole/RoleService,
Location UUID/LocationAccessPolicy, Audit/Outbox и DjangoEmailProvider.
Параллельных справочников сотрудников, объектов и ролей нет.

EmployeeAssignment хранит историю и один активный primary. Изменение объекта
сохраняет должность, юрлицо, подразделение и действующий вход. Юрлицо владельца
объекта не становится автоматически юрлицом трудоустройства.

Заявка содержит структурированное ФИО, Location, хеш пароля, email confirmation и
хеш собственного status capability. До подтверждения/одобрения рабочий User не
создаётся. Capability не является JWT. Публичный repeat не перезаписывает заявку
и не раскрывает employment/grants владельца email. Confirmation заменяет status
capability; после решения/отмены/истечения хеш пароля очищается.

Invite фиксирует обязательный объект и access plan до создания Employee.
Одноразовый токен хранится только как SHA-256; подписанная ссылка восстанавливается
для доставки по ID/версии без raw-token в БД/Outbox/Audit. Хеш permissions роли
требует reissue при изменении grants. Defaults: 7 дней, employee_objects_viewer,
один employment Location как scope, selected/пустая ответственность. Email binding
проверяется при отправке и подтверждении. Reissue отзывает старую ссылку и отменяет
её незавершённую заявку. Used/expired/revoked не активируют аккаунт.

Пользователь разрешил публично показывать все действующие Objects: только UUID
и название. Closed/archived и их потомки исключаются; unclassified legacy не
классифицируется. Трудоустройство и отдельная историческая ответственность
selected/all не дают grants. All включает новые действующие Objects; при увольнении
или деактивации история ответственности закрывается, права/сессии отзывает lifecycle.

Нормализованный email уникален через Lower(Trim(email)). Старые значения не меняются;
коллизии останавливают миграцию с числом групп, без автоматического объединения.
Вход SPA разрешает исходное написание email. ФИО не служит ключом сопоставления.
Existing Employee с work_email требует явной привязки. Returning обычный аккаунт
требует EmployeeService.reactivate, email-bound invite и account_access.reactivate;
старые активные EmployeeRole отзываются. Staff/superuser/legacy UserRole возвращают
отдельным account lifecycle, низкая роль invite не восстанавливает их привилегии.

## Матрица полномочий

| Действие | Требование |
|---|---|
| Публичная форма/минимальный перечень | Anonymous, общий атомарный DB rate limit |
| Confirmation/status/resend/cancel | Соответствующий capability, без рабочего JWT |
| Scoped requests list/detail/count/approve/reject | people.registration.manage: Location либо явный LegalEntity/global |
| Invite create/revoke/reissue | people.invitation.manage в объекте |
| Делегировать role/access_locations | people.invitation.delegate каждого объекта; та же действующая собственная роль/context либо superuser |
| Связать существующего Employee | Явный выбор + people.employee.manage по People policy |
| Изменить ответственность | People manage + разрешённые объекты, без новых grants |
| All ответственность | Superuser либо отдельный global people.responsibility.all |
| Основной объект | People manage + people.assignment.manage + делегируемый объект; primary history |
| Объектная роль | People manage + ограниченная делегация, отдельные assign/revoke |
| Legacy employees/{id}/roles | Superuser либо явный global role.manage; employee.manage недостаточно |

Пилот делегирует Location/registration Location permissions и собственный просмотр
профиля/адаптации/запросов изменения данных. Global, OrgUnit, LegalEntity, Team,
собственные права других доменов и legacy grants не конвертируются в object scope;
их назначают отдельно уполномоченным RBAC workflow. Минимальная роль допускается
только с точным набором location.view/location и people.profile.view_self/own;
изменение этого набора блокирует её использование как default. Backend/UI используют один
allowlist. All ответственность означает Objects данной установки, не all доступ;
для нескольких независимых компаний нужен отдельный tenant-контракт.

При принятии заново проверяются inviter lifecycle (включая inactive Employee
superuser), полномочия/периоды/роль и состояние объекта. Email/Employee/invite/request
блокируются транзакционно; object write lock сериализует привязки с archive/move.
Старые API create/resend больше не выпускают необъектные ссылки. Ранее выпущенные
legacy ссылки сохраняют контракт; новые нельзя активировать password-only API.

Новые обычные аккаунты этого сценария закрыты от legacy API Tasks, Checklists,
Sensors, Incidents, Analytics, Knowledge, Learning, Organization и iiko. Старые
Facility/Zone не имеют утверждённого Location mapping; IsAuthenticated-only доступ
не должен превращать минимальную роль в право записи. Старые аккаунты сохраняют
поведение, personal dashboard новых аккаунтов не раскрывает legacy Tasks.

## Миграции, API и UI

accounts 0004: read-only collision preflight + unique index.
employees 0016: добавочные request/invite поля и ответственность; 0017: два новых
permissions и минимальная роль в существующем каталоге, только если кода ещё нет;
0018: permission snapshot; 0019: shared rate buckets. Existing User/Employee/UUID,
assignments/grants не меняются; EmployeeRole при migrate/seed не назначаются.
Удаляются только истёкшие технические counters, не бизнес-история.

Public /api/public/v1/registration/: GET locations; POST submit, confirm, status,
resend, cancel, invitation. Старый /api/public/v1/register/ требует новый полный
контракт. Capability передаётся в body; fragment удаляется из history; no-store.
Public role/scope/employee/extra fields отклоняются. Internal /api/internal/v1/registration/:
requests, invitations (+options/revoke/reissue), employees/{UUID}/objects/access/employment.
Scope queryset применяется до pagination, detail, filter и counts.
UI /register и /people/registration (aliases registrations/invitations), Employee card
показывает отдельно трудоустройство, ответственность, роли/scopes и их изменения.

## Consumers и доставка

Notification worker регистрирует registration.mail.requested и
registration.invite_mail.requested: verify/review/approve/reject/invite.
Нужны enabled + SMTP backend; console/file/dummy не печатают ссылки и не считаются
доставкой. До SMTP сохраняется durable UNKNOWN marker. Автоматический repeat только
для явно retryable, не ambiguous ошибок; сохраняются attempts/delay/accepted_recipients.
Crash/ambiguous outcome останавливает повтор; явный resend создаёт новую generation.

registration_events.REGISTRY подтверждает уже транзакционно сохранённые read models
регистрации, привязок, ответственности и RBAC. Legacy registration/invitation без
object context не перехватываются. Receipt **не является доставкой**. SMTP acceptance
не доказывает внешний inbox. Raw-token/password/текст provider errors не логируются.

## Release/restore

Фактические проверки: [REGISTRATION_ACCEPTANCE.md](REGISTRATION_ACCEPTANCE.md).
Инструкция: [REGISTRATION_USER_GUIDE.md](REGISTRATION_USER_GUIDE.md).
Рабочая restored DB и внешний SMTP/inbox NOT VERIFIED; deployment NOT PERFORMED.

GO: актуальный production drift/migrations/grants, отсутствие normalized-email
коллизий, существующие Employee associations и минимальная роль, публичные действующие
Objects. Исходные images/env/services зафиксировать; закрыть регистрацию/writers.
Свежий согласованный защищённый DB/media rollback backup, off-host checksums и restore
именно его файлов. На копии полный migrate/seed_permissions/collectstatic/check/drift,
repeat plan [], сравнение User/Employee/assignments/grants, API/browser и согласованный
inbox smoke. Проверить multi-worker throttling и consumers. Затем pinned images,
проверенный init пяти миграций, restricted smoke, workers/queues и открытие регистрации.
Production шаги требуют отдельного разрешения.

STOP: email collisions, изменение исходных UUID/grants, неверный image/plan,
неподтверждённые backup/restore, scope leak, email failed/unknown, отсутствие согласующих.
До новых записей откатить images/согласованную recovery точку. После новых регистраций
blind restore запрещён: закрыть writes, сохранить свежие DB/media/Outbox/receipts/audit,
инвентаризировать новые User/Employee/назначения/решения и согласовать их сохранение
с recovery owner. Обратные миграции с удалением таблиц не заменяют план данных.
