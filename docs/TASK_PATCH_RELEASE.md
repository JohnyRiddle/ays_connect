# Патч задач и corporate Telegram: выпуск и восстановление

Дата: 13.10.2026. Base: `origin/main` `62c61ed`; runtime checkpoint `713be6b`
совпадает с ним, разница только в документации регистрации. Изолированный worktree
`codex/task-telegram-patch`; commit/push и черновой PR разрешены пользователем 13.10.2026.
Точный Git SHA фиксируется в PR и итоговом отчёте. Merge и deployment требуют **отдельного разрешения конкретного RC**.
Прежнее разрешение выпуска регистрации на этот патч не распространяется.

## Состав и данные

Work: responsible_department, deadline flags, blocking priority, настройки
календарных сроков, head routing, department/object-bound executor choices,
watcher policy, participant lookup, historical deadline inheritance, overdue notice.
Шаблоны получают явное nullable responsible_department. Projects: обязательный
planned_end_at, проверка конфликтов, наследование и отключённый active priority.
Notifications: существующие binding/delivery модели расширены lease полями;
новый service-only pull API использует те же NotificationIntent/Delivery/Attempt.
UI: скрыты новые заявки, формы назначения/наблюдателей/упоминаний и диагностика.

Новые задачи проекта наследуют его объект, если собственный объект не задан
шаблоном. Назначения проверяются по этому объекту; членство в подразделении или
primary_location не заменяют явный grant. Старые object FK массово не заполняются.

Добавочные migrations:

- `notifications/0006_notificationdelivery_lease_expires_at_and_more.py`;
- `work_tasks/0005_task_deadline_from_project_and_more.py`;
- `work_tasks/0006_taskoverduenotice.py`;
- `work_tasks/0007_tasktemplate_responsible_department.py`;
- `work_tasks/0008_task_deadline_is_manual.py`.

Выпущенные migrations не редактируются. Никакого переноса или удаления заявок,
tasks, targets, grants, attachments или pending location.*. Новые nullable
department поля остаются пустыми до явного административного заполнения.
Исторический raw priority сохраняется; `active_priority=null` у проектной задачи.
Runtime умеет читать проектный дедлайн старой связанной задачи без её own due_at;
при следующем изменении проекта наследуемый срок фиксируется с историей.

## Обязательные gates перед разрешением выпуска

1. Зафиксировать итоговый commit, diff и immutable backend/frontend/worker images.
   Этот checkout начинается от checkpoint до незакоммиченного опубликованного
   дизайна. Перед выпуском интегрировать патч с окончательным согласованным commit
   дизайна. Сборка старого frontend не должна откатить фирменный интерфейс, карточки,
   историю обновлений и последние Objects изменения. Повторить проверки итогового RC.
2. Снять свежий snapshot рабочей БД и media в подтверждённое защищённое хранилище,
   восстановить **отдельную** копию с выключенным внешним egress. Synthetic upgrade
   тест не заменяет этот gate. До/после сравнить таблицы, UUID/number/targets,
   history/attachments и fingerprints RolePermission/EmployeeRole/User.
3. Выполнить реальный штатный init копии: migrate, seed_permissions,
   collectstatic и owner/mode проверки; repeat migrate plan/check/drift должны быть
   пустыми. Новые permissions не выдаются людям автоматически.
4. Инвентаризовать старые tasks/templates без departments, projects без deadline,
   конфликтующие сроки и отсутствующие/неактивные/неоднозначные manager positions.
   Составить согласованный административный список изменений. При необходимости
   приостановить только затронутые recurrence rules; не потерять историю occurrences.
5. Проверить API и UI копии под реальными существующими scoped personas; не
   расширять grants ради PASS. Проверить historical requests/attachments. Снять
   отдельные количества pending location.*; не обрабатывать их новым task consumer.
6. Выдать разработчику бота HTTPS staging URL и отдельный service credential
   защищённым каналом. Установить pull/username/public-base настройки до запуска
   consumer. Проверить действующий corporate transport и отсутствие двойного sender.
7. Реальная привязка и delivery acceptance: ответственный, исполнитель, несколько
   наблюдателей, роли-дубли, mention, revoke до begin, 429/backoff, blocked,
   неизвестный исход и повтор ack. Проверить message ID и сообщения в Telegram.
8. Подготовить отдельную защищённую frozen rollback-точку DB+media, согласовать
   write-window, владельца восстановления и retention. Проверить restore из неё
   до переключения. Online snapshot для rehearsal не является frozen rollback-точкой.

Только после всех применимых gates запросить разрешение merge/deployment именно
этого RC. Проверить health/ready, штатные workers, HTTP HTTPS, миграционный план,
диагностику Telegram и fingerprint grants после переключения.

## Восстановление

До внешних writes можно вернуть предыдущие pinned images и согласованную frozen
DB/media точку по проверенному runbook. После новых writes **не выполнять blind
restore**: сначала закрыть writes, сохранить новый tail DB/media/Outbox/Audit,
оценить совместимость старого кода и восстановить или перенести новые записи
по отдельному согласованному плану. Предпочтительно forward fix.

Additive columns не удалять при возврате images. `migrate work_tasks 0004` в рабочей
БД запрещён как штатный rollback: удалит новые department/lease/notice данные.
Migration downgrade применяется лишь в изолированном synthetic upgrade test.
Для остановки внешней отправки отключить service credential/pull и worker-cycle
по согласованному плану; не переключать unknown автоматически на direct sender.
Сохранить неизвестные исходы и результаты Telegram для ручной сверки.

## Ограничения

Production deployment, fresh production-copy rehearsal, frozen protected rollback
point и реальная доставка Telegram пока **NOT PERFORMED / NOT VERIFIED**.
Staging URL не предоставлен. Токен Telegram получен в чате, но не используется
пакетом и не хранится в репозитории. Перед production следует перевыпустить его
и передать разработчику защищённо; AYS service credential выпускается отдельно.

Новый consumer выбирает только allow-listed task events; исторический backlog task.*
может создать уведомления. До первого запуска зафиксировать cutoff и согласовать
обработку backlog с оператором; не удалять события. Упоминания отправляют ссылку,
а не содержимое обсуждения. Watcher UI добавляет выбранных последовательно, поэтому
ошибка части пачки не откатывает уже добавленных. Физическая очистка media не добавлена.

Нельзя гарантировать отсутствие дублей после Telegram send и потери ack.
Даже после begin существует короткое окно между проверкой доступа и внешним send.
Бот обязан надёжно хранить собственные отправки и не повторять неоднозначные исходы.
