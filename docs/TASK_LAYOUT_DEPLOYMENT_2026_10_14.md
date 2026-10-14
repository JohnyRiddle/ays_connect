# Выпуск интерфейса чек-листов и наблюдателей — 14.10.2026

Feature commit: `cf5a47a31c21cdcb87a45e32a78e346e8925bb3a`. PR #5 объединён:
https://github.com/JohnyRiddle/ays_connect/pull/5.
Frontend опубликован `2026-10-14T10:36:55.527736+00:00` (UTC) на https://ays-connect.ru.

Чек-листы: нумерация и прогресс, раскрываемые комментарии, компактные
сохранённые ответы. Параметры задачи разгружены. Наблюдатели добавляются из
выпадающего поиска по имени/фамилии, существующие исключены из результатов.
Красное текстовое действие «× Удалить» требует inline подтверждения.

Проверки: TypeScript PASS; browser **8/8** на 1280/390 px; immutable production
Vite build PASS. Public HTTPS **10/10 PASS**, включая точные hashes
index и новых JS/CSS на обоих доменах. Backend/шесть workers **7/7 healthy**,
их контейнеры, images и StartedAt не менялись; миграции не запускались.
Actual HTTPS owner UI существующей задачи: checklist/progress, поиск,
Escape, крестик и mobile без overflow PASS; **0 HTTP writes**.
Первые попытки live helper остановились на неоднозначном option locator и
проверке скрытого мобильного меню; уточнённый helper прошёл, продукт не менялся.

Frontend image: `sha256:c9baf581a7ccd3ca1dd5725cf315412cc1dc8b0cff968d7dbcd0203f02cf57bc`.
Перед переключением полный frontend volume сохранён в EFS off-host:
`I:\AYS Connect\TaskPatch\task-layout-release-20261014T103526Z/frontend-before.tar.gz`.
SHA256: `6ee89330576de4e7bc1589609da226bad007c4b702d401810c2dd48f1e8d94c0`.
Архив прочитан, index/assets проверены. Предыдущий image и Compose сохранены,
на сервере подготовлен `/home/ivan/ays-task-layout-cf5a47a31c21/restore-previous.sh`.
Возврат требует только восстановления предыдущего frontend, БД не затрагивается.
Публикация сохраняет старые hashed assets и атомарно заменяет index.html.
Compose-current, Telegram operational wrapper и его защищённый state обновлены
на новый frontend override; Telegram остаётся выключен. Protected evidence:
`I:\AYS Connect\TaskPatch\task-layout-release-20261014T103526Z`. Три отложенных Telegram source-файла не входят в выпуск.
