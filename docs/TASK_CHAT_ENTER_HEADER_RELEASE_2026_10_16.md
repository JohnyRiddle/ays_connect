# Enter и согласование из заголовка чата — выпуск 16.10.2026

По явному запросу выполнены commit/push/merge и publication.
[PR #14](https://github.com/JohnyRiddle/ays_connect/pull/14), merge
`0aee5e9b213afc0af8115eed15dd5914603baaa4`, frontend RC `c984b6580750a8017edee310d6f27b51acd58f70`.

Enter отправляет непустое сообщение, Shift+Enter вставляет строку. В @списке
Enter выбирает сотрудника. IME/autorepeat/busy не отправляют сообщение.
Кнопки запроса убраны из пузырьков; одна кнопка справа в заголовке открывает
панель выбора разрешённого сообщения, согласующего и обязательного текста.
Источник фиксируется при открытии. Плашки согласований/история остаются в чате.
Прежние endpoint/payload/RBAC/Task/SLA сохранены, backend не менялся.

## Проверки

Browser **25/25 PASS**, TypeScript/Vite/diff PASS. Сценарии на 1280/390 px:
Enter/Shift+Enter, IME, пустое сообщение, @ выбор перед отправкой, расположение
кнопки, разрешённые источники, точный source в POST, обязательность текста,
сохранение плашки, Escape/focus, прежние poll/draft/scroll и checklist тесты.

Production HTTPS **16 PASS** на обоих доменах; SHA256 index/JS/CSS совпали.
Browser **10/10 PASS**, desktop/mobile, **0 HTTP write attempts**: кнопка в
заголовке и отсутствие её в сообщениях; настоящий source/approval-options API;
Escape/focus; Shift+Enter и Enter в пустом поле; автоопрос с сохранением draft.
Непустой Enter с POST проверен локально mock API, реальные сообщения для
production UI-проверки не отправлялись. Core **7/7 healthy**, backend health RC
`376a8dd001657c655a80c0f999a6eba3f8afbfe9` сохранён. Полный backend gate не повторялся, поскольку
source backend/deployment/compose и backend image не менялись.

## Публикация и восстановление

Frontend-only, UTC `2026-10-16T06:36:44.234280+00:00`, без простоя/перезапуска backend.
Backend/workers/DB/proxy сохранили container IDs и состояние. Index заменён
атомарно после копирования assets, **34 прежних assets** сохранены.
БД, миграции и права не менялись. Telegram/receiver выключены.

Перед заменой сохранены **41 файлов** frontend volume. Архив EFS off-host
и LUKS mirror сверен SHA256, распакован; размеры/хеши всех восстановленных
файлов совпали. Отдельный DPAPI-носитель ключа на F: проверен test-passphrase.
Владелец Иван, хранение 90 дней без автоудаления. SHA256 архива
`7763e4f5be6fab2aa132da8e852fd476f45e84f9f7e5300259e7a24c71d1dbd8`.
Защищённые source/configs/archive/proofs/screenshots: `I:\AYS Connect\TaskPatch\chat-header-release-20261016T063456Z`.
Frontend image `sha256:e50a1716b000617867aa706ba1f8094b6cb507d544aa1e554c1a9115491360a2`.
Backend image сохранён `sha256:38e56d23ab34f964b48983c10360ca714c3fb8f60ad995ca3bfbb5a3e202dea9`.

Operational wrappers/current-stack/Telegram metadata согласованы с новой
frontend RC; backend RC сохранён. Три отложенных Telegram source-файла не вошли
в выпуск. Секреты, дампы и пользовательские данные в Git не добавлялись.
Статус **DEPLOYED_ACCEPTED**.
