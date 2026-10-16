# Упрощённая форма согласования — выпуск 16.10.2026

По явному запросу выполнены commit/push/merge и production deployment.
[PR #15](https://github.com/JohnyRiddle/ays_connect/pull/15), merge
`c0f738344a352685bbcbacd564ec285e0897f012`; backend/frontend RC `2d12c15b7084b1cb09ba1ff892f185b13afabbc2`.

Форма содержит только согласующего и текст, работает и в пустом чате. Текст
публикуется отдельным сообщением с плашкой согласования. Новый GET task-level
approval-options проверяет прежние права и object scope без создания данных.
POST без comment атомарно создаёт TaskComment, TaskApproval, Audit/Outbox.
Ошибка откатывает всё, command_id защищает от повторов и конфликтов, task lock
сериализует конкурентные ретраи. Старые comment-specific API сохранены.
Ни Task.save, ни изменение Task.status/SLA/сроков/приоритета/назначений не вызываются.
История, повторные раунды, отмена и Notification Engine сохранены. Новых grants,
watchers или миграций нет. Telegram/receiver выключены.

## Проверки до переключения

Свежая production-копия `2026-10-16T07:02:16.701946+00:00`: **204 таблицы**, изолированная internal
network, без открытых портов/внешних уведомлений. Init/seed_permissions/
collectstatic, сверка исходников и сохранности исходных строк PASS.
План миграций пуст. Полный PostgreSQL gate с production password hasher:
**717/717 PASS**, parallel=3. Профильные локальные **61/61 PASS**.

API **22/22 PASS** на копии и production, настоящие роли Ивана/Юлии и объект
OhMyGesh, с полным rollback тестовых задач/сообщений/согласований/уведомлений.
Включены прежний контракт/прямой выбор, scope, раунды/история, неизменность Task,
checklists/version, mention flags, новые кандидаты, публикация сообщения,
повтор/конфликт, отсутствие комментария после ошибки, неизменность всех Task
полей после нового запроса. Новых прав не выдавалось; проверены прежние 7 staff,
2 approval-участника, 6 grants и 51 объект Юлии.

Browser **26/26 PASS**, TypeScript/Vite/check/drift/diff PASS. Пустой чат,
два поля, отказ/сохранение формы/повтор с прежним command_id, новая плашка,
нет кнопки при отказе права, прежние keyboard/poll/draft/scroll сценарии.
Standalone OpenAPI **8 paths / 9 operations / 12 schemas**, validation PASS;
общая схема сохраняет прежние legacy diagnostics.

## Восстановление и публикация

Frozen UTC `2026-10-16T07:08:58.354556+00:00`, окно записи **93.109 с**.
БД, media и frontend сохранены EFS off-host и LUKS mirror; SHA256 сверены.
До переключения восстановлены **204 таблицы** и оба файловых
архива с проверкой содержимого. После init все исходные 204 таблицы совпали;
повторный migration plan пуст. Отдельный DPAPI-носитель ключа на F: проверен
test-passphrase. Владелец Иван, хранение 90 дней без автоудаления. После открытия
записи откат кода не должен стирать новые данные или понижать миграции.

Frontend index заменён атомарно; **35 прежних assets**
сохранены. Финальные HTTPS **16 PASS** на обоих доменах, SHA256 index/JS/CSS,
health.version соответствует RC. Core **7/7 healthy**. Production browser
**10/10 PASS**, 1280/390 px: два поля и реальные approval-options, отсутствие
источника/preview, кнопка в заголовке, Escape/focus, Shift+Enter/пустой Enter,
автоопрос и сохранение draft. **0 HTTP write attempts**, тестовые сообщения
через браузер в production не отправлялись. Реальное создание проверено через
API rollback, как описано выше. Visual QA mobile PASS.

Operational wrappers/current-stack/Telegram metadata согласованы с новым
backend/frontend RC. После запуска workers **11 identity/org/RBAC таблиц**
неизменны. Два контейнера изолированной копии остановлены; backups сохранены.
Защищённые source/configs/dump/media/frontend/proofs/screenshots: `I:\AYS Connect\TaskPatch\simple-approval-release-20261016T070109Z`.
Backend image `sha256:6ae6f09650ddf9265caeb3d6877a62ea3dfd3bc0134cfc88cf681d21d51c195a`.
Frontend image `sha256:28f485cba3b5aff04f1d6e27640da2f97197cd373acf65436c5b3d094613bfd3`.
Три отложенных Telegram source-файла не вошли в Git. Секреты, дампы и
пользовательские данные не добавлялись в репозиторий. Статус **DEPLOYED_ACCEPTED**.
