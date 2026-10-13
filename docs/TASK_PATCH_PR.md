# Предлагаемый PR: задачи сотрудников и API корпоративного Telegram-бота

Новые обращения создаются каноническими задачами вместо новых Service Requests.
Ответственный определяется по подразделению, исполнитель ограничен активными
сотрудниками подразделения с доступом к объекту. Сохраняются история и действующие
grants; подразделения старых задач/шаблонов заполняются явно администратором.

Патч добавляет пять приоритетов и календарный расчёт от создания, защищённое
изменение срока с причиной, проектные задачи без активного приоритета с дедлайном
проекта, выбор нескольких наблюдателей и поиск UUID-упоминаний в существующем чате.
Участие наблюдателя само по себе не даёт управление задачей.

Для @AYS_ai_expert_bot реализован отдельный service-only API: одноразовая привязка,
claim/begin/ack/fail, повторная проверка активности и доступа, срок резервирования,
идемпотентность, блокировка и unknown для неоднозначных отправок. Notification,
Audit и Outbox переиспользуются; pending location.* не удаляются и не выбираются
task consumer. Участники с несколькими ролями и mention не дублируются на событие.

Схемы и контракт: `docs/telegram-bot/`; инструкция: `docs/TASK_PATCH_USER_GUIDE.md`;
миграции, границы и gates восстановления: `docs/TASK_PATCH_RELEASE.md`;
результаты проверок: `docs/TASK_PATCH_ACCEPTANCE.md`.

Только добавочные migrations. Нет новых service types, нового бота, миграции
legacy Tasks или автоматического переноса заявок. Нет исходных сторонних dirty-файлов,
credentials, DB/media или production writes. Base — актуальный `origin/main` 62c61ed;
незакоммиченный опубликованный дизайн должен быть интегрирован отдельно перед выпуском.

**Release readiness CONDITIONAL:** fresh production-copy init/preservation 201 таблицы,
38/38 focused и защищённый frozen DB/media/frontend restore PASS. Реальный Telegram
transport: два сообщения (15024/15025), получатель @ivan_ays подтвердил; API harness
проверил link/claim/begin/ack, role dedup и revoke. Полный серверный 672 repeat
resource-limited; прежний local 672/672 и browser 6/6 PASS сохраняются отдельно.

До выпуска нужны реальные departments/heads (сейчас 0 units/4 old tasks без department),
интеграция опубликованного дизайна, HTTPS staging и постоянный bot adapter.
Текущая версия production возобновлена без deployment; финальная frozen точка
и merge/deployment требуют отдельного согласованного RC.
Даты/SHA/границы: `docs/TASK_PATCH_REHEARSAL.md`.
