# Компактная переписка задач — выпуск 16.10.2026

По явному запросу выполнены commit/push/merge и production publication.
[PR #13](https://github.com/JohnyRiddle/ays_connect/pull/13), merge
`7f069541b614fd1ba205b0f8c5808e957fe632aa`, frontend RC `ec41c15729b4d9b1a0ef44a21b19064b348f2e49`.

Сообщения — пузырьки «Отправитель: сообщение», свои справа по UUID employee
профиля, остальные слева. Короткое время рядом, разделители дней. Внутренние
сообщения, согласующий/статус и запрос согласования оформлены плашками.
Существующие история, раунды и действия раскрываются из плашки согласования.
Поле ввода **48 px**, ручное расширение до 220 px. Автообновление, @,
черновик/scroll, API и права сохранены. Метки доставки/прочтения не выдумываются.

## Проверки

TypeScript/Vite/diff PASS. Browser **21/21 PASS**, 1280/390 px, светлая/тёмная
темы: переносы/длинный текст, свои/чужие сообщения, плашки, обязательный текст
решения, компактный composer, прежние checklist/watcher/mention/poll сценарии.
Production source backend/deployment/compose сравнен с действующей backend
версией — изменений нет. Полный backend gate не повторялся: image не менялся.

После публикации HTTPS **16 PASS** на обоих доменах, SHA256 index/JS/CSS совпали;
health.version сохранил backend RC `376a8dd001657c655a80c0f999a6eba3f8afbfe9`. Core **7/7 healthy**.
Финальный browser **12/12 PASS**, **0 HTTP write attempts**, desktop/mobile:
настоящий scoped comments API (TASK-000006), автоматический повтор без reload,
draft/нижняя граница, свои пузырьки/двоеточие, поле 48 px, focus/mobile и
открытие прежней формы согласования из плашки без POST.
Для проверки прихода использован только GET-only overlay поверх настоящего
ответа API; комментарии/уведомления в production не создавались. Первый browser
прогон остановился по таймауту 15 с ожидания overlay-сообщения; повтор без
изменений продуктового кода завершил все 12 проверок. Visual QA screenshots PASS.

## Публикация и откат

Frontend-only, UTC `2026-10-16T06:13:30.500941+00:00`, без простоя. Backend/workers/DB/proxy
сохранили container IDs и состояние. Новые assets скопированы, index заменён
атомарно; **32 прежних assets** сохранены.
Перед заменой архив frontend volume **39 файлов** сохранён EFS off-host
и LUKS mirror, SHA256 сверен. Архив распакован; все размеры/хеши восстановленных
файлов совпали. Отдельный DPAPI-носитель ключа на F: проверен test-passphrase.
Владелец Иван, хранение 90 дней без автоудаления. SHA256 архива
`e0ab72c6422048a56bda0df5d414d45210e899bcf6e75d9c3d847d65117e3232`.

Защищённые source/configs/archive/proofs/screenshots: `I:\AYS Connect\TaskPatch\chat-bubbles-release-20261016T061202Z`.
Frontend image `sha256:2131751a1d8a63259b88742a09670980f977551e4f55ef975d34b95913bea5ad`.
Backend image сохранён `sha256:38e56d23ab34f964b48983c10360ca714c3fb8f60ad995ca3bfbb5a3e202dea9`.
Operational wrappers и frontend metadata согласованы с новой сборкой;
backend RC, БД, миграции и права сохранены. Telegram/receiver выключены.
Три отложенных Telegram source-файла в выпуск не вошли. Секреты, архивы и
пользовательские данные в Git не добавлялись. Статус **DEPLOYED_ACCEPTED**.
