# Последние уведомления — выпуск 16.10.2026

По запросу пользователя выполнены commit/push/merge и production publication.
[PR #18](https://github.com/JohnyRiddle/ays_connect/pull/18), merge
`373f3ac63f3a63c7f06fc913734f2e51b7c20525`, frontend RC
`2e1bee5e8c3218abffeb5a9341731880b8d0709c`.

После штатного read-all колокольчик загружает общий список и показывает пять
последних уведомлений, включая прочитанные. История доступна при повторном
открытии и после перезагрузки. Badge отражает только непрочитанные. Ошибки
показываются внутри списка с повтором; загрузка отделена от пустой истории.

Локально TypeScript/Vite/diff PASS, профильный browser **5/5 PASS**.
Production HTTPS **16 PASS**, index/JS/CSS SHA256 на обоих доменах,
browser **14/14 PASS** при 1280/390 px: read-all, повторное открытие,
история после reload, синхронизация с центром и размеры меню.
Notification API в браузерной проверке подменён: **10 mock POST**, **0 реальных
HTTP write attempts**; реальные уведомления не изменялись. Core **7/7 healthy**.

Публикация `2026-10-16T16:40:56+07:00`, frontend-only, без простоя.
Backend/workers/DB/proxy сохранили container IDs; backend RC
`2d12c15b7084b1cb09ba1ff892f185b13afabbc2`, image
`sha256:6ae6f09650ddf9265caeb3d6877a62ea3dfd3bc0134cfc88cf681d21d51c195a`
не менялись. Backend gate повторно не запускался: его source не изменён.
Frontend image `sha256:02c4a033ba1b2997de8de8a60578bd7ed86d92d2dc35dc8b2f27a40771ecc406`.
Атомарная замена index, **39 прежних assets** сохранены.

Точка восстановления frontend volume: **47 файлов**, EFS off-host и LUKS mirror,
SHA256 архива `efb06380a9e6e404fcada96caf320ac9b01189dc780a799580cc7cd604d9848f`.
Распаковка и сравнение содержимого PASS, ключ отдельного DPAPI-носителя проверен.
Владелец Иван, хранение 90 дней без автоудаления. Защищённые proofs/source/backup:
`I:\AYS Connect\TaskPatch\notification-history-release-20261016T093800Z`.

Operational wrappers/current-stack согласованы. БД, миграции и права не менялись;
Telegram/receiver выключены. Три отложенных Telegram-файла не вошли в commit.
Статус **DEPLOYED_ACCEPTED**.
