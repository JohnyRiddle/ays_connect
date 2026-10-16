# Автоматическое обновление чата — выпуск 16.10.2026

По явному разрешению выполнены commit/push и публикация.
[PR #12](https://github.com/JohnyRiddle/ays_connect/pull/12), merge
`1e78f94b5666b5ba7367c1023bdd7322bce3d049`, frontend RC `1b943d0475eecf33c4cbeb7cc9659b4d953ce08f`.

Чат получает сообщения через существующий scoped API каждые 5 секунд
и при возврате во вкладку. Скрытая вкладка не опрашивается. Черновик и @
сохраняются; новые сообщения видны у нижней границы, чтение выше сохраняет
прокрутку. Последовательные GET, отмена при смене задачи, timeout 15 секунд,
автоматическое восстановление после сетевой ошибки; отказ доступа очищает
переписку. Собственная отправка не перекрывается старым ответом опроса.

## Проверки

До выпуска browser **19/19 PASS**, TypeScript/Vite/diff PASS. Новые сценарии
1280/390 px: приход сообщения без reload, сохранение draft/scroll,
503 recovery, edit/delete, hidden/visible, slow GET + own send, focus dedupe.
Production build использует `/api/v1` и RC; backend/deployment/compose source
сравнены с действующей backend-версией — изменений нет. Полный backend gate
не повторялся, поскольку backend image не менялся.

После публикации HTTPS **16 PASS** на обоих доменах, SHA256
index/JS/CSS совпали. Backend health.version остался `376a8dd001657c655a80c0f999a6eba3f8afbfe9`.
Core **7/7 healthy**. Browser **8/8 PASS**, 1280/390 px: настоящая scoped
загрузка комментариев, следующий автоматический GET без reload, сохранение
черновика/нижней границы, focus refresh и отсутствие overflow.
Новое сообщение для UI-проверки добавлено только GET-only overlay поверх
настоящего ответа API; в production комментарии не создавались.
**0 HTTP write attempts**, реальные сообщения/уведомления не отправлялись.

## Публикация и восстановление

Frontend-only, UTC `2026-10-16T05:12:10.957773+00:00`. Простоя нет, backend/workers/DB/proxy
сохранили container IDs и состояние. Новые assets скопированы, затем index
заменён атомарно; **30 прежних assets** сохранены.
БД, миграции и права не менялись. Telegram/receiver выключены.

Перед заменой сохранён архив frontend volume **38 файлов**.
EFS off-host и LUKS mirror сверены SHA256, архив распакован, размеры/хеши
восстановленных файлов совпали. Отдельный DPAPI-носитель ключа на F:
проверен test-passphrase. Владелец Иван, хранение 90 дней без автоудаления.
SHA256 архива `e58a027e6365c196fc7b9f11fecd10a43873cedd820468349def27d339694656`.

Защищённые source/configs/archive/proofs/screenshots: `I:\AYS Connect\TaskPatch\chat-live-release-20261016T051039Z`.
Frontend image `sha256:53f254b31713d279ca668a5f88efbee42cd14081c36e2edff37122b116d87150`.
Backend image сохранён `sha256:38e56d23ab34f964b48983c10360ca714c3fb8f60ad995ca3bfbb5a3e202dea9`.
Operational wrappers и frontend metadata согласованы с новой версией;
backend RC сохранён. Три отложенных Telegram source-файла не вошли в Git.
Секреты, архивы и пользовательские данные в репозиторий не добавлялись.
Статус **DEPLOYED_ACCEPTED**.
