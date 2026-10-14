# AYS Connect → корпоративный Telegram-бот: контракт v1

Дата: 13.10.2026. Бот: **@AYS_ai_expert_bot**. Это документация реализованного
кода ветки патча; методы опубликованы в production 13.10.2026.
Новый бот не создаётся. Токен Telegram в пакет не входит.

13.10.2026: два реальных тестовых сообщения на @ivan_ays подтверждены получателем;
link/claim/begin/ack и дедупликация проверены через API harness копии.
14.10.2026 по уточнению владельца подготовлен штатный путь подключения из профиля
и доставка ответственному через notification_worker, transport `direct`.
Постоянное включение остановлено сетевым blocker: production не достигает
Telegram. Канал выключен до настройки исходящего доступа/HTTPS-прокси.
[Production, проверки и продолжение](../TELEGRAM_PROFILE_PRODUCTION_2026_10_14.md).
[Границы проверки и evidence](../TASK_PATCH_REHEARSAL.md).

## Адреса и инвентаризация

| Контур | Base URL | Статус |
|---|---|---|
| Изолированная локальная разработка | `http://localhost:8000` | только фиктивные данные; не доступен боту извне |
| Тестовый HTTPS-контур | требуется от оператора | URL не предоставлен, не утверждён |
| Production | `https://ays-connect.ru` | действующий адрес платформы; новые методы патча NOT DEPLOYED |

До патча в checkpoint `713be6b` уже есть `TelegramAccount`, хешированные
`TelegramLinkToken`, профильные link/status/unlink, webhook, прямой Telegram sender,
NotificationIntent/Delivery/DeliveryAttempt, preferences, quiet hours и статус
`unknown`. Outbox `notification.requested` материализуется worker-командой
`process_notifications`. Наличие кода не подтверждает настройки действующего бота
или фактическую доставку. Webhook `POST /api/integrations/telegram/webhook/`
с `X-Telegram-Bot-Api-Secret-Token` сохранён для прежнего direct-контра.
Не заменять webhook корпоративного бота командой `configure_telegram_webhook`.

Патч добавляет потребление task.* событий и pull API. Список ниже содержит только
реально зарегистрированные маршруты. Ответы из Telegram, управление задачами,
произвольное чтение People/Tasks/attachments/grants ботом **не реализованы**.

## Реализованные методы

| Статус | Method | Path | Назначение | Авторизация |
|---|---|---|---|---|
| Уже был, расширен | GET | `/api/internal/v1/notification-channels/telegram/` | своя привязка, блокировка, последний результат доставки | Employee JWT |
| Уже был, усилен | POST | `/api/internal/v1/notification-channels/telegram/link/` | одноразовый код и deep-link | Employee JWT |
| Уже был, усилен | POST | `/api/internal/v1/notification-channels/telegram/unlink/` | отключение и отзыв неиспользованных кодов | Employee JWT |
| Добавлен | POST | `/api/integrations/corporate-telegram/v1/bindings/redeem/` | атомарное погашение кода | Bot service bearer |
| Добавлен | POST | `/api/integrations/corporate-telegram/v1/deliveries/claim/` | резервирование пачки | Bot service bearer |
| Добавлен | POST | `/api/integrations/corporate-telegram/v1/deliveries/{delivery_id}/begin/` | повторная проверка доступа перед отправкой | Bot service bearer |
| Добавлен | POST | `/api/integrations/corporate-telegram/v1/deliveries/{delivery_id}/ack/` | подтверждение Telegram message ID | Bot service bearer |
| Добавлен | POST | `/api/integrations/corporate-telegram/v1/deliveries/{delivery_id}/fail/` | категория ошибки | Bot service bearer |

Полные схемы запросов/ответов и security schemes: [openapi.json](openapi.json).
Файл генерируется из этих восьми маршрутов командой
`python manage.py export_bot_contract --output ../docs/telegram-bot/openapi.json`.

## Привязка

1. Авторизованный активный сотрудник выпускает ссылку в настройках уведомлений.
   Link POST не требует тела. Ответ содержит `bot_username`, `start_parameter`,
   `deep_link`, `expires_at`. Настройка `TELEGRAM_BOT_USERNAME=AYS_ai_expert_bot`.
2. Корпоративный бот получает `/start <start_parameter>` в **private** чате и
   передаёт код, Telegram user ID и private chat ID в redeem.
3. AYS атомарно проверяет срок, однократность, активность сотрудника и чужую
   активную привязку. Username — только необязательный атрибут. Grants не меняются.
4. Сотрудник может отключить и выпустить новый код. Старые привязки сохраняются
   неактивными. Перенос активной привязки другого сотрудника запрещён.

TTL кода по умолчанию **900 секунд**, `TELEGRAM_LINK_TOKEN_TTL`.
Новый выпуск отзывает прежние действующие коды. Private chat ID должен быть
положительным и равняться user ID. Не использовать @username или ФИО для привязки.

Обезличенный запрос:

```json
{"code":"ONE_TIME_CODE_FROM_PROFILE","telegram_user_id":100001,"private_chat_id":100001,"username":"synthetic_recipient"}
```

```sh
curl -X POST "$AYS_BASE/api/integrations/corporate-telegram/v1/bindings/redeem/" \
  -H "Authorization: Bearer $AYS_BOT_SERVICE_CREDENTIAL" -H 'Content-Type: application/json' \
  -d '{"code":"ONE_TIME_CODE_FROM_PROFILE","telegram_user_id":100001,"private_chat_id":100001}'
```

Ответ: `{"linked":true,"employee_id":"11111111-1111-4111-8111-111111111111"}`.
Не писать код и credentials в логи разработчика, shell history или баг-репорты.

## Доставка: claim → begin → send → ack/fail

`claim` принимает `{"limit":25}` (1–100). Возвращает `{"results":[]}` при пустой
очереди. TTL резервирования **120 секунд**, `TELEGRAM_BOT_LEASE_SECONDS`.
В каждой записи:

```json
{
  "notification_id":101,"delivery_id":202,
  "event_id":"22222222-2222-4222-8222-222222222222",
  "event_type":"task.comment_added","event_version":1,
  "recipient_employee_id":"11111111-1111-4111-8111-111111111111",
  "telegram_chat_id":100001,
  "task_id":"33333333-3333-4333-8333-333333333333",
  "task_number":"TASK-000123","task_title":"Синтетическая задача",
  "location":null,"change":"TASK-000123: новое сообщение — вас упомянули в обсуждении",
  "priority":"normal","deadline":"2026-10-16T05:00:00Z","actor":null,
  "url":"https://ays-connect.ru/tasks/33333333-3333-4333-8333-333333333333",
  "occurred_at":"2026-10-13T05:00:00Z",
  "lease_token":"44444444-4444-4444-8444-444444444444",
  "lease_expires_at":"2026-10-13T05:02:00Z"
}
```

`location`, `actor`, `priority` и `deadline` могут быть null. Для проекта priority
всегда null. Actor предоставляется лишь при доступности сотрудника получателю.
Пакет не содержит вложений или тела сообщения; обсуждение открывается по ссылке
в AYS. Срок/заголовок пакета отражают доступную актуальную карточку, время и тип
события сохраняются из Outbox. ID события стабилен при повторной выдаче;
новый резерв получает новый lease_token. Номер notification_id не является UUID.

До отправки вызвать `begin` с `{"lease_token":"..."}`. Отправлять только после
HTTP 200 и `send_allowed:true`. Повторный begin отвечает `send_allowed:false`;
если первый ответ потерян, не считать второй begin разрешением на новую отправку.
Активность, Task policy, объект, актуальная видимость внутреннего комментария,
preferences и прежняя привязка проверяются ещё раз. Отзыв до begin отменяет
ожидающее уведомление. Между положительным begin и Telegram send остаётся короткое
внешнее окно: распределённую транзакцию с Telegram API контракт не обещает.

После успешного `sendMessage` вызвать ack:

```sh
curl -X POST "$AYS_BASE/api/integrations/corporate-telegram/v1/deliveries/202/ack/" \
  -H "Authorization: Bearer $AYS_BOT_SERVICE_CREDENTIAL" -H 'Content-Type: application/json' \
  -d '{"lease_token":"44444444-4444-4444-8444-444444444444","telegram_message_id":"98765"}'
```

Тот же ack с тем же message ID идемпотентен; другой ID — ошибка. Ack допустим
поздно для того же начатого резерва в unknown, если точный message ID сохранён
ботом. Сохранять send outcome и очередь ack надёжно на стороне бота.

Fail: `{"lease_token":"...","category":"ambiguous"}`.

| Category | Значение | AYS status | Действие бота |
|---|---|---|---|
| retryable | подтверждённый отказ без отправки: rate limit/временный отказ | retry до 5 попыток, затем failed | можно повторно claim после backoff |
| blocked | Telegram подтвердил блокировку/недоступный private chat | failed, привязка delivery-disabled | пользователь разблокирует бота и повторно привяжет |
| permanent | подтверждённая постоянная ошибка | failed | исправить причину, оператор решает повтор |
| ambiguous | timeout/reset или потеря результата после начала send | unknown | не отправлять автоматически снова, ручная проверка |

Retry backoff: `min(3600,60*2^attempts)` секунд. Для Telegram 429 передать
`retry_after_seconds` (1–86400); используется максимум provider delay и backoff.
Без begin истёкший резерв можно безопасно получить снова. После begin истечение
переводит в unknown. Claim/Outbox processing не равны доставке: delivered ставится
только по ack с Telegram message ID. Абсолютное отсутствие дублей при сбое между
Telegram send и ack **не гарантируется**. Fail и ack не принимают произвольный текст
ошибки или payload; чужой/старый lease_token отвергается.

## События и получатели

Версия payload: **1**. Совместимые поля могут добавляться; неизвестные поля
игнорировать. Неизвестную major-версию не отправлять, сообщить оператору.
Список фактически материализуемых task.* событий: created, published, assigned,
reassigned, updated, started, waiting, resumed, deadline_changed, comment_added,
comment_updated, watcher_added, overdue, completed, sent_to_review, review_accepted,
review_rejected, reopened, cancelled. Упоминание включено в уведомление сообщения;
отдельный `task.comment_mentioned` остаётся в истории, второго уведомления не даёт.
Просрочка фиксируется worker один раз на задачу/дедлайн.

Только ответственный, исполнитель, активные наблюдатели и упомянутые сотрудники,
уже имеющие доступ. Один Employee с несколькими ролями получает одну Notification
на исходное событие. Упоминание не даёт прав; добавление наблюдателя не даёт
управления назначениями, сроками или завершением через PARTICIPATING.

## Авторизация, конфигурация и ошибки

У бота отдельная сервисная identity `corporate-telegram-bot`, без EmployeeRole,
superuser или входа в обычные JWT API. Её bearer принимают только пять bot методов.
Оператор выдаёт случайный сильный service credential защищённым каналом; сервер
получает только SHA256 в `TELEGRAM_BOT_SERVICE_TOKEN_SHA256` (нижний hex).
Credentials не равны Telegram BOT_TOKEN. Настройки находятся вне Git.

Для подключения: `TELEGRAM_BOT_SERVICE_ENABLED=1`,
`TELEGRAM_DELIVERY_TRANSPORT=pull`, `NOTIFICATIONS_TELEGRAM_ENABLED=1`,
`WORK_TASK_PUBLIC_BASE_URL=https://ays-connect.ru` (на тесте его HTTPS-адрес).
`TELEGRAM_BOT_SERVICE_PREVIOUS_TOKEN_SHA256` позволяет короткое окно ротации;
после переключения бота удалить прежний hash. Для полного отзыва отключить service
и убрать оба hash. Rate limit по умолчанию **120/min** на service identity,
`TELEGRAM_BOT_API_RATE`. Profile link — **5/hour**, `BINDING_THROTTLE_RATE`.
HTTP допустим лишь в локальной изоляции; внешний контракт — HTTPS.

Pull резервирует **новые WORK_TASK_EVENT** доставки. Существующие non-task direct
доставки не перехватывает; их токен/transport должен оставаться прежним. Не включать
одновременно внешний sender и прямой worker для одних и тех же task deliveries.
Проверить реальную конфигурацию корпоративного бота до cutover.

HTTP 400 — неправильные поля/code/lease/state; 401 — credential отсутствует или
отозван; 403 — profile policy; 429 — throttle (соблюдать Retry-After). Ошибка имеет
`error.code`, `error.message`, `error.details`; domain code привязки находится также
в `error.details.code`. Значимые domain codes: telegram_link_token_invalid/used/
expired, telegram_private_chat_required, telegram_employee_inactive,
telegram_account_already_linked/conflict, telegram_pull_disabled, lease_invalid/
expired, send_not_started, send_already_started, ack_conflict.
Не повторять 400/401 слепо. Ошибка сети после begin/send считается неоднозначной.

## Подключение и разделение ответственности

AYS: схема, migrations, Audit/Outbox, проверки доступа, bindings, lease/ack/fail,
diagnostics и publication после отдельного разрешения. Разработчик бота: обработка
deep-link, проверка private chat, service credential storage, Telegram send,
надёжная фиксация message ID, ack/fail/retry и UX сообщений. Оператор: HTTPS теста,
настройка подразделений/руководителей, secret rotation и права тестовых получателей.

Порядок: согласовать тестовый URL → выдать service credential защищённо → бот
реализует 5 методов → сотрудник проходит профильный deep-link → проверить
создание/назначение/сообщение/упоминание ответственному, исполнителю и нескольким
наблюдателям → проверить отзыв до begin, blocking/429/ambiguous/повтор ack → проверить
отдельно delivered/message ID и фактическое сообщение на телефоне.

Получатель `@ivan_ays` подтверждён private сообщением с согласованной меткой;
числовые user/chat ID установлены и сохранены только в защищённом evidence.
**Real transport + copy API harness — PASS**: два сообщения 15024/15025,
получатель подтвердил оба. **Постоянный HTTPS adapter — NOT VERIFIED**.
[Границы проверки](../TASK_PATCH_REHEARSAL.md). Пакет разработчику не отправлялся.
