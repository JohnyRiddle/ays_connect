# Final runtime and release

Registration contract and production release verified for `713be6b755950fcce5f5bf22d9fc05743c8f0053`.
[Release evidence](REGISTRATION_RELEASE.md). AssignmentTarget automation integrated
separately: canonical employee create/activation, self approval and invite acceptance
ensure one audited target under Employee row lock; replay reuses existing target.
Inactive/pending/blocked employees excluded from new lookup/resolution, historical
FKs preserved. Lookup requires explicit employee.view scope and filters before list,
search/detail/count; no grants added by target creation. Preview-default command
`ensure_employee_assignment_targets` has explicit audited --apply/superuser actor;
production backfill not run by this release. No additional schema migration.
First-release approval uses existing superusers; scoped ordinary-manager setup not
automatically assigned and not a blocker. All original dirty files remain outside Git.

# Регистрация и объектные назначения — требования 12.10.2026

Ветка codex/registration, база main 5d9da353ee552af3b0c2182c374f132d0e91e2ce.
Production регистрации не обновлялся. iikoCard — отдельный этап.

## Контракт

Email обязателен, формат проверяет API, нормализация strip/lower; User уникален
через Lower(Trim(email)). Владение почтовым ящиком не проверяется. Старое написание
email сохраняется, нормализованный вход работает; коллизии останавливают миграцию
без объединения аккаунтов. Отчество необязательно, пароль и подтверждение обязательны.

Self submit сразу создаёт pending/«Ожидает согласования». Рабочие User/Employee и
назначения не создаются до решения уполномоченного согласующего. Pending заявка
сразу видна в его scoped списке. Собственный статус, причина отказа и отмена доступны
по приватному capability из ответа submit, сохранённому в sessionStorage. Capability
не является JWT и не даёт рабочие данные. При утрате capability требуется обращение
к согласующему; восстановления через email нет. Повтор не раскрывает оригинальный
status token, employment или grants и не заменяет чужой пароль/ФИО.

Invite уже является согласием доступа. Submit с действующей ссылкой транзакционно
создаёт заявку и активирует аккаунт: approved, одно принятие, один User/Employee и
primary. Обязательный Location, роль, scope и ответственность неизменяемы публичной
формой. Email binding означает только совпадение нормализованного введённого адреса,
не подтверждение владения ящиком. Ссылка копируется в UI для передачи сотруднику.
Default: семь дней (максимум), минимальная утверждённая роль, один employment scope.

Писем нет: verify/review/approve/reject/invite mail events не создаются. Retired
confirm/resend HTTP endpoints отвечают 410 и ничего не меняют. UI не содержит
ожидания подтверждения/resend; старая #verify ссылка сообщает об изменении порядка.
Legacy password-only activation не принимает новый object invite.

## Сущности, права и lifecycle

Переиспользуются User, Employee, RegistrationRequest, EmployeeInvitation, Location
UUID, EmployeeAssignmentService, RoleService, существующие Permission/Audit/Outbox.
Новых каталогов объектов/сотрудников нет. Не классифицируются Facility/Zone, нет
автоматического mapping, переноса legacy или назначения all существующим людям.

Employment — один primary с историей; изменение сохраняет должность, org/legal и
вход. Юрлицо объекта не становится работодателем автоматически. Responsibility
selected/all — отдельная история, не grants; all охватывает новые действующие
объекты данной установки. Multi-company isolation требует отдельного tenant-контракта.
Access — реальные Role/EmployeeRole scopes. All responsibility не означает all access.

| Действие | Полномочие |
|---|---|
| Public submit/minimal locations/status/cancel | Anonymous + shared PostgreSQL rate limit; own status capability |
| Scoped requests list/detail/count/filter/approve/reject | people.registration.manage на Location либо явный LegalEntity/global |
| Invite issue/revoke/reissue | people.invitation.manage |
| Role/access delegation | people.invitation.delegate для каждого объекта; точная собственная роль/context либо superuser |
| Existing Employee link/responsibility | People manage; явный выбор, никакого FIO auto-match |
| All responsibility | Отдельный global people.responsibility.all либо superuser |
| Primary replacement | People manage + assignment.manage + делегируемый Location |
| Legacy role assignment | Отдельный global role.manage либо superuser |

Минимальная роль допускается только с location.view/location и
people.profile.view_self/own, добавленные write grants блокируют её как default.
Пилот делегирует Location permissions и безопасный собственный просмотр. Global,
OrgUnit/LegalEntity/Team/legacy/own других доменов не превращаются в object scope.
Inviter lifecycle, grants/периоды/hash состава роли и доступность объектов повторно
проверяются при принятии. Архив/закрытие и inactive inviter запрещают принятие.
Email/Employee/invite/request/object locks защищают конкуренцию и archive/move.

Existing active User не активируется заново. Existing Employee связывают явно по
проверенному invite или административному решению. Returning обычный User требует
штатной People реактивации и account_access.reactivate, прежние EmployeeRole отзываются.
Staff/superuser/legacy accounts возвращаются отдельным lifecycle. Отсутствие проверки
ящика не отменяет обязательного явного решения для существующего Employee.

Новые обычные аккаунты закрыты от legacy Tasks/Checklists/Sensors/Incidents/Analytics/
Knowledge/Learning/Organization/iiko API: Facility/Zone mapping не утверждён, а
IsAuthenticated-only доступ не должен давать записи минимальной роли. Старые аккаунты
сохраняют поведение; новые canonical People/Work/Requests/Projects под действующими policies.

## API, миграции, consumers

Public /api/public/v1/registration/: locations, submit, status, cancel, invitation;
confirm/resend — tombstones 410. Старый public/register требует полный новый контракт.
Internal /api/internal/v1/registration/: requests, invitations/options/revoke/reissue,
employees/{UUID}/objects/access/employment. Querysets scoped до pagination/detail/count.
UI /register, /people/registration и отдельные employment/responsibility/roles в карточке.
Tokens/password не попадают в Audit/Outbox/log; no-store, fragment очищается.

Шесть additions: accounts 0004 + employees 0016–0020. Первые пять — identity preflight,
request/invite/responsibility, permissions/minimal-role без EmployeeRole backfill,
role hash и shared rate counters. 0020 убирает email_pending из choices и отменяет
только старые object-context email_pending заявки с очисткой password hash, Audit и
registration.cancelled Outbox. Существующие pending legacy/approved Users/grants не
изменяются. Старую отменённую invite reservation перевыпускают через reissue; автоматической
активации при миграции нет. Поля email_confirmed_at/mail_generation остаются для истории,
не используются как gate и не выдаются в новом request API как подтверждённое владение.

Старые непрочитанные mail jobs становятся failed/REGISTRATION_MAIL_DISABLED, retry=None;
processed история сохраняется. Worker tombstone consumer никогда не вызывает SMTP и
отключает случайные старые pending/retry jobs при любом email config. Новых mail jobs нет.
registration_events подтверждает внутренние read model/state события. Это не доставка
уведомлений; отсутствие SMTP является нормальным поддерживаемым режимом.

## Условия выпуска и откат

[Проверки](REGISTRATION_ACCEPTANCE.md), [инструкция](REGISTRATION_USER_GUIDE.md).
Внешняя SMTP-доставка полностью исключена из release gates. Обязательны свежая
изолированная restored production DB/media, collision preflight, preservation реальных
User/Employee/RolePermission/EmployeeRole/primary history и настройка согласующих/делегации.

GO: зафиксировать drift/migrations/images/services, проверить eligible минимальную роль,
действующие публичные Objects и существующих superuser-согласующих; scoped менеджеры не являются gate первого выпуска. Закрыть writes/регистрацию и остановить writers, включая notification worker
старой версии до init, чтобы старый SMTP consumer не отправил накопленные письма. Получить
fresh согласованный защищённый DB/media rollback backup + off-host SHA + restore.
На копии выполнить полный migrate/seed_permissions/collectstatic/check/drift, повторный
пустой plan и сравнение grants/UUID. Проверить retirement old mail/requests, отсутствие
mail events при обоих сценариях и process_notifications при включённом SMTP без отправки.
Пройти API/browser no-SMTP, denied/scoped/related сценарии и согласование. Затем согласованный
production init шести additions, pinned images, restricted smoke, workers/Outbox, открыть доступ.
Production release разрешён завершающим ТЗ и выполнен для итогового RC; см. REGISTRATION_RELEASE.md.

STOP: email collision, изменённые исходные grants/UUID, неверный plan/image, неподтверждённый
backup/restore, утечка scope, автоматическая отправка registration mail или отсутствие approver.
До новых записей откатить согласованную точку/images; после новых User/Employee/решений blind
restore запрещён. Закрыть writes, сохранить fresh DB/media/Outbox/Audit, согласовать сохранение
новых записей с recovery owner. Обратные миграции не заменяют план данных.
