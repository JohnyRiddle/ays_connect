# Прочитать все при открытии колокольчика — выпуск 16.10.2026

По подтверждению пользователя выполнены commit/push/merge и publication.
[PR #17](https://github.com/JohnyRiddle/ays_connect/pull/17), merge
`d830c82b7191968ad0a6c91157168ca5ea26fb43`; frontend RC `bb08c55ea8d98b725d2dbee1db7496745e26c7a6`.

Открытие списка вызывает штатный read-all endpoint, индикатор полностью
исчезает после подтверждения. Снимок пяти пунктов остаётся в раскрытом списке,
уведомления не удаляются. При раннем открытии snapshot загружается до read-all.
Ошибка сохраняет count и кнопку повтора. Новые поступления при уже открытом
списке не читаются автоматически до следующего открытия. Предыдущий revision
guard, синхронизация с центром событий и mobile positioning сохранены.

Профильный browser **4/4 PASS**, TypeScript/Vite/diff PASS: 1280/390 px,
полное чтение 15 пунктов вместо пяти, пагинация/ошибка/повтор, центр и late GET.
Backend/deployment/compose source совпадает с действующей backend RC, image
не менялся, поэтому полный backend gate не повторялся.

Финальные production HTTPS **16 PASS**, SHA256 index/JS/CSS на обоих доменах,
health RC backend `2d12c15b7084b1cb09ba1ff892f185b13afabbc2` сохранён, core **7/7 healthy**.
Production browser **10/10 PASS**, desktop/mobile: открытие помечает все 15,
не выполняя индивидуальные read; badge исчезает, preview и ссылка сохранены,
список в экране; single/all read из центра синхронизируются, отступ меню 28 px.
Notification GET/POST в проверке полностью подменялись в браузере: **6 mock POST**,
**0 production HTTP write attempts**, реальные уведомления не затронуты.

Frontend-only publication UTC `2026-10-16T08:51:24.888800+00:00`, без простоя. Backend,
workers/DB/proxy сохранили container IDs и состояние. Index заменён атомарно,
**38 прежних assets** сохранены. До замены защищённый архив
frontend volume **46 файлов** EFS off-host/LUKS mirror сверен SHA256,
распакован: размеры/хеши восстановленного содержимого совпали. Ключ отдельного
DPAPI-носителя на F: проверен test-passphrase. Владелец Иван, хранение 90 дней
без автоудаления. SHA256 архива `09dd6cab862428cdb8eecb3b45cc4139b188291791bbee201e3cb8a6d75dfc42`.

Защищённые source/configs/archive/proofs/screenshots: `I:\AYS Connect\TaskPatch\notification-open-all-release-20261016T084932Z`.
Frontend image `sha256:3f405038351a74d3aaf54bc15b65ed31e280a48c1c56b2fd883daeb9e48b37b7`.
Backend image сохранён `sha256:6ae6f09650ddf9265caeb3d6877a62ea3dfd3bc0134cfc88cf681d21d51c195a`.
Operational wrappers/current-stack/frontend metadata согласованы с новой RC.
БД/миграции/API/RBAC сохранены, Telegram/receiver выключены. Три отложенных
Telegram source-файла не вошли в Git. Секреты и пользовательские данные не
добавлялись в репозиторий. Статус **DEPLOYED_ACCEPTED**.
