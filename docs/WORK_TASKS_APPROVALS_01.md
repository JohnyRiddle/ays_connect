# WORK-TASKS-APPROVALS-01 — аудит и контракт

## 16.10.2026 — запрос без выбора сообщения (локальная доработка)

Форма в заголовке чата содержит только согласующего и обязательный текст.
Работает в пустом чате. Новый GET `/tasks/{id}/approval-options/` проверяет
активность/Task/Object scope, approval.view/request и task.comment, не создаёт
сообщений и не выдаёт прав. Старый comment-specific endpoint сохранён.

POST `/tasks/{id}/approvals/` принимает прежний payload с UUID comment, либо
новый без comment: approver/text/command_id. Без comment в одной транзакции
создаются публичное сообщение из текста, TaskApproval и прежние Audit/Outbox.
Ошибка откатывает всё. Нет скрытого выбора последнего/чужого сообщения.
Идемпотентность под task row lock (NO KEY UPDATE): одинаковый command_id
возвращает прежний результат; другой текст/задача/согласующий дают конфликт.
Параллельные ретраи создают одно сообщение и одну историю. Task не сохраняется:
все поля, SLA, статусы, сроки и назначения неизменны. Для публикации сообщения
нужно уже существующее task.comment; новых grants/watchers не создаётся.

Старая форма/интеграции с явным comment совместимы; history/раунды/отмена/
уведомления работают через существующий ApprovalService. После успешной отправки
frontend читает comments и approvals, показывая запрос с плашкой в чате.
Отказ сохраняет форму и тот же command_id для повтора. Миграций нет.

Проверки: **61/61 PostgreSQL PASS**, включая rollback, concurrency, повторы,
Task.save guard, cross-task conflict, права; **26/26 browser PASS** на 1280/390 px,
пустой чат, два поля, отказ/повтор, новая плашка, отсутствие кнопки без права.
TypeScript/Vite/check/drift/diff PASS. Standalone OpenAPI **8 paths / 9 operations /
12 schemas**, validation PASS. Общая схема сохраняет прежние legacy diagnostics.
Изменения локальные: commit/push/production deployment не выполнялись.


Дополнение 15.10.2026: по новому запросу подготовлен **прямой выбор согласующего**.
Оно заменяет исходное требование предварительного упоминания/доступа к задаче
в описании ниже. После явного разрешения опубликовано в PR #8, runtime `e24a928`.
[Финальная приёмка](SIMPLE_CHECKLISTS_DIRECT_APPROVAL_RELEASE_2026_10_15.md).

## Прямой выбор без наблюдателей

Автор опубликованного комментария открывает «Запросить согласование», выбирает
сотрудника в поле «Согласующий», вводит текст и отправляет. Предварительное
@упоминание и добавление наблюдателя не требуются. Обычное упоминание по-прежнему
ничего не запускает. Самосогласование запрещено.

Список кандидатов ограничен доступным инициатору справочником сотрудников,
активностью учётной записи, доступом к объекту, существующими правами task.view
и approval.view/respond с учётом prospective participation. Просмотр списка
не выдаёт доступ. Внутренний комментарий требует уже действующего explicit
task.comment_internal; приглашение это право не создаёт.

После атомарного создания TaskApproval назначенный согласующий считается
участником именно этой задачи для task.view/task.comment и четырёх approval
permissions. Роль и scope должны уже разрешать эти операции; запрос не создаёт
roles/grants/TaskWatcher, не даёт права менять статус/назначения/сроки или чек-лист.
TaskSelector, API и Notification Engine используют одну policy. Для такого
участия перепроверяется доступ к объекту; после отзыва grants доступ закрывается.
История сохраняет основание участия после решения/отмены, пока действуют права.
Ни одно поле Task или SLA при создании/решении согласования не меняется.

API payload и семь путей остаются прежними; approval-options теперь возвращает
всех подходящих кандидатов, а не только упомянутых. OpenAPI обновлён и валиден.
Миграции и изменения production-данных для этой доработки не требуются.

## Исходный аудит и контракт опубликованного выпуска

Аудит 15.10.2026 выполнен до реализации. База: ede0ac8, ветка содержит
незакоммиченные доработки task-usability-fixes, включая @ composer. Они сохранены;
три отложенных Telegram source-файла не относятся к патчу.

- Production Task: work_tasks; приёмка TaskService.accept/reject меняет status,
  потому не используется для независимых согласований.
- TaskComment и UUID TaskCommentMention уже существуют; упоминание публикует
  task.comment_mentioned. Оно само по себе не должно создавать согласование.
- TaskAccessPolicy/TaskSelector, LocationAccessPolicy и внутренние комментарии
  задают scope. Запрос не даёт доступа и не добавляет наблюдателя автоматически.
- AuditService/DomainEventService работают в транзакции. NotificationIntent с
  WORK_TASK_EVENT маршрутизирует in-app/Telegram, проверяя доступ при доставке.
- Политика участия ограничивает watchers определённым набором permissions;
  approval permissions должны работать с уже разрешённым просмотром/комментированием,
  не расширяя visibility задачи для новых получателей.
- OpenAPI: drf-spectacular. Неизменяемость истории требует PostgreSQL trigger,
  чтобы bulk update/delete не обходили model guards.

## Контракт реализации

Отдельный TaskApproval для пары исходный комментарий/упомянутый согласующий.
Инициатор — автор исходного комментария. Явный запрос требует текст; обычное
упоминание ничего не запускает. Самосогласование не допускается.
PENDING → APPROVED либо CLARIFICATION_REQUESTED решением согласующего с текстом.
Инициатор может отправить следующий раунд из CLARIFICATION_REQUESTED или APPROVED
(новое явное подтверждение с текстом), либо отменить незакрытый запрос.
CANCELLED — терминальное состояние. Решения прошлого раунда неизменяемы.
При нескольких упомянутых сотрудниках их согласования независимы.

API требует UUID command_id для идемпотентности и version согласования для
optimistic conflict. Identity/snapshot и append-only записи защищены в БД.
Новые permissions: task.approval.request/respond/cancel/view; автоматических
выдач существующим ролям нет. Решать может только назначенный согласующий,
отменять — инициатор либо администратор с отдельным действием; все проходят scope.
Автор/согласующий должны иметь доступ к задаче/объекту и внутреннему комментарию.

Никаких вызовов TaskService, Task.save/update, SLA, deadlines или назначений.
История согласования, Audit и события создаются атомарно, уведомления несут
только нейтральное событие и ссылку, без тела комментария/ответа. Получатели —
инициатор/согласующий (без рассылки всем сотрудникам). Доставка перепроверяет
актуальный доступ; staging не отправляет реальные Telegram/email сообщения.

Staging и тесты — синтетические данные и изолированная БД. Production deployment,
миграции, права и данные production в рамках этого патча запрещены до разрешения.

## Реализация и данные

`TaskApproval` хранит UUID задачи/исходного комментария, инициатора, согласующего,
неизменяемый снимок текста и внутренней видимости, status, round_number, version.
`TaskApprovalEvent` — append-only журнал с UUID команды, последовательностью,
раундом, актором, действием, переходом и обязательным текстом.
Миграции `0010_comment_approvals`, `0011_approval_history_guards` аддитивные:
две новые таблицы, constraints/triggers, только каталог четырёх permissions.
Существующим ролям/сотрудникам grants не выдаются. Зависимость People уже
покрыта старой work_tasks.0009; связь с новой фазой регистрации не добавляется.

PostgreSQL защищает историю от UPDATE/DELETE, snapshot/identity — от изменения,
переходы/sequence — от нарушения, а deferred trigger требует запись истории
в той же транзакции. Admin согласований только для чтения. Сами тексты решений
хранятся в immutable history, в Audit/Outbox идут только идентификаторы/переходы.
Обычные комментарии по-прежнему редактируются/мягко удаляются; snapshot согласования
сохраняется. Текущая внутренняя видимость комментария может ужесточить доступ
к истории, но не расширить его ниже исходного snapshot.

## API

Все адреса под `/api/internal/v1/tasks/{id}/`:

- GET/POST `approvals/` — список / явный запрос;
- GET `comments/{comment_id}/approval-options/` — допустимые упомянутые;
- GET `approvals/{approval_id}/` — состояние и immutable history;
- POST `approvals/{approval_id}/approve/` — «Согласовано»;
- POST `approvals/{approval_id}/clarify/` — «Запросить уточнение»;
- POST `approvals/{approval_id}/resubmit/` — новый раунд;
- POST `approvals/{approval_id}/cancel/` — отмена согласования.

Создание: comment UUID, approver UUID, text, command_id UUID.
Действия: text, **version согласования**, command_id UUID. Task.version не передаётся.
Пустые/пробельные тексты — 400, недоступный scope — 403/404,
устаревшая version или повтор UUID с другим содержимым — 409.
Идентичный повтор не создаёт второй истории/Audit/Outbox/notification.
Generic PATCH/DELETE согласований и истории отсутствуют.
Повтор запроса после сетевого сбоя использует прежний UUID; изменение содержания
формы создаёт новый UUID. При конфликте UI обновляет состояние, решение повторно
автоматически не применяет.

[Standalone OpenAPI](openapi/work-tasks-approvals-01.yaml): 7 путей, 8 операций,
12 schemas, UUID path parameters, mandatory text/version/idempotency, 400/401/
403/404/409. Выделенный контракт прошёл drf-spectacular schema validation.
Общая старая схема репозитория сохраняет 255 diagnostics (48 unique errors)
в других API и 360 warnings; у новых approval операций diagnostics нет.
Это не заявление о полностью исправленной общей OpenAPI-схеме.

## Уведомления

Новые события `task.approval.request/approve/clarify/resubmit/cancel` включены в
прежний WORK_TASK_EVENT Notification Engine. Получатель — другая сторона
согласования, без дубликата актору и без рассылки всей компании.
Intent/recipient/channel дедуплицируются прежними constraints. Тело исходного
комментария, запросов и решений в Telegram не включается: нейтральное описание
события и ссылка на задачу. Bot packet имеет approval id/event/status/round.
Materialization и доставка перепроверяют Task/Object/internal/approval-view scope;
согласование не создаёт доступ к задаче или объекту. Реальная внешняя отправка
на staging отключена; production bot token, webhook и transport не менялись.

## Проверки 15.10.2026

- PostgreSQL full suite: **708/708 PASS**, parallel=3, локальный тестовый MD5 hasher
  (на staging логин проверен со штатным password hasher).
- Профильный прогон Tasks Collaboration + TaskPatch + Approvals + Notifications:
  **104/104 PASS**. Из них 22 новых approval tests: все Task columns/history
  неизменны на переходах и всех статусах Task, запрет Task.save, раунды,
  atomic rollback, stale/idempotent conflict, RBAC/internal/object scope,
  назначенный согласующий без superuser override, история после правки/удаления
  комментария, PostgreSQL direct SQL/bulk tamper, race двух решений,
  deferred guard, Notification Engine/dedup/revoke-before-delivery.
- Реальный localhost API и две обычные учётные записи: **2/2 E2E** (1280/390 px),
  mention без автоматического согласования, explicit request, обязательный текст
  обоих решений, clarification → round 2 → approved, history, round 3/cancel,
  полный Task detail до/после равен, нет horizontal overflow.
- Прежние browser usability/checklists: **12/12 PASS**, TypeScript/Vite PASS.
- Django check / makemigrations --check / diff check PASS.
- Seed guard без explicit local staging flag отказывает до создания данных.
- Notification staging fingerprint: Task/status/deadline и 22 SLA models неизменны;
  10 approval intents, 10 in-app delivered, 10 Telegram CHANNEL_DISABLED,
  0 внешних попыток (до повторного E2E на собранном интерфейсе).

Первый полный прогон выявил лишнюю автоматически созданную зависимость
0010 от employees.0020; она мешала тесту старого upgrade регистрации.
Удалена ненужная зависимость, затем полный 708/708 прошёл. Ранние два новых
теста исправлены под реальные completed timestamp/Telegram linked_at constraints;
продуктовые проверки не ослаблялись.

## Локальный staging

Интерфейс: http://127.0.0.1:3035 — отдельная собранная Vite production bundle
с API http://127.0.0.1:8035; backend слушает только loopback.
PostgreSQL 17: 127.0.0.1:55489, отдельная синтетическая DB
`ays_approval_staging_20261015`. Workers recurrence/SLA/Telegram не запущены.
Внешние Telegram/email каналы false, почта locmem. Production DB не копировалась.

Тестовая задача: http://127.0.0.1:3035/tasks/3eacad4a-01d6-485a-af70-03c154bbff0f.
Только demo-аккаунты этого localhost staging:
`requester@approvals.demo.invalid`, `approver@approvals.demo.invalid`;
пароль обоих `Demo12345!` — публичный синтетический demo password, не production.

Как проверить:
1. Инициатор пишет в чат с @ и выбирает согласующего из подсказки, отправляет.
2. Под сообщением выбирает «Запросить согласование», сотрудника и текст.
3. Согласующий входит во втором браузере/контексте, открывает эту задачу.
4. «Запросить уточнение» либо «Согласовано» открывает обязательный текст ответа.
5. Инициатор после уточнения открывает новый раунд. Старые решения — в истории.
6. Task остаётся «В работе», его deadline/priority/назначения/version не меняются.

Reproducible fixture: `manage.py seed_approval_staging --fixture-output <file.json>`
требует `AYS_APPROVAL_STAGING=1`, DEBUG, loopback DB с префиксом
`ays_approval_staging`, выключенные внешние каналы и пустую БД. Данные не сбрасывает.
Конфигурация запуска/fixture/логи и bundle —
`C:\Users\riddl\.codex\tmp\approval-staging`.
E2E: `AYS_APPROVAL_FIXTURE=<file.json>` и
`playwright test -c playwright.approvals.config.ts` против запущенного staging.

## Граница staging на момент подготовки

Ветка `codex/work-tasks-approvals-01` содержит также сохранённые предыдущие
незакоммиченные usability-исправления, на которых основан чат с @.
Commit/push/PR/production deployment не выполнялись. Две approval migrations,
новые permissions и выдача grants в production ждут отдельного разрешения и
production-copy/frozen gate. Telegram egress/доставка на реальный аккаунт здесь
не проверялись и не включались. Три отложенных Telegram source-файла сохранены.

Финальная проверка собранного staging интерфейса: повторные E2E **2/2 PASS**.
После перезапуска локального API публичный staging OpenAPI содержит актуальные
7 путей/8 операций и корректный array available_actions. Повтор Notification
Engine: **20 intents / 20 in-app delivered / 20 Telegram CHANNEL_DISABLED**,
**0 внешних попыток**, прежние fingerprints 25 Task/SLA моделей совпали.
Frontend index SHA256:
`bc94e9f534d69bc7c519a44e682d991170f093354920251fe9030974b4c77b21`.
Скриншоты проверки: `.codex/tmp/approval-staging/approval-desktop.png`,
`approval-mobile.png`; synthetic данные, без production credentials.

## Публикация 15.10.2026

После явного разрешения выполнены commit/push и PR #6/#7. Отдельно согласована
операционная выдача четырёх approval permissions семи сотрудникам в роли
`staff_tasks_participant_20261014`, только scope `participating`; автоматическая
выдача существующим ролям в миграциях не добавлялась. Поиск участников отделён
от фильтра названия родительской задачи с сохранением Task/Object scope.
Полный финальный прогон на свежей production-копии: **709/709 PASS**;
14 транзакционных API-проверок с rollback, staging browser **2/2 PASS**,
прежние UI-проверки **12/12 PASS**. Telegram остаётся выключенным.
Frozen-точки и финальная приёмка: [отчёт выпуска](WORK_TASKS_APPROVALS_RELEASE_2026_10_15.md).
