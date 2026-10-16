# Счётчик уведомлений и отступ меню — выпуск 16.10.2026

По явному запросу выполнены commit/push/merge и production publication.
[PR #16](https://github.com/JohnyRiddle/ays_connect/pull/16), merge
`f2fc9e079ad29e6269267912fbc3e53da5ad18fc`, frontend RC `b4ebc838fc6b97178d5f94fba87f26f27a90c6e8`.

При открытии колокольчика пять показанных пунктов помечаются прочитанными,
остальные не затрагиваются. Preview остаётся на месте, подтверждённо прочитанные
отмечены стилем read. «Прочитать все» читает весь доступный набор. Счётчик берёт
server count; single/all read из центра событий синхронизирует колокольчик,
поздний GET не возвращает старое число. Ошибка чтения не обнуляет индикатор.
Ссылка из задачи ведёт на /#notifications. Mobile dropdown удерживается в экране
и ограничен по высоте с прокруткой. Закрытие mention popup по-прежнему не читает
уведомление. Подпункты всех раскрытых разделов меню сдвинуты вправо на 16 px
(padding-left 28 вместо фактических 12), заголовки разделов сохранены.

## Проверки

Основной browser suite **30/30 PASS**, после финального CSS correction повтор
четырёх notification/geometry сценариев **4/4 PASS**. TypeScript/Vite/diff PASS.
Проверены server count при 40 уведомлениях и странице 25, частичный отказ/read-all
ошибка, late GET, preview, связь центра событий и колокольчика, mobile 390 px.
Source backend/deployment/compose сравнен с действующей backend RC — изменений
нет. Полный backend gate не повторялся, поскольку backend image не менялся.

Production HTTPS **16 PASS** на обоих доменах, SHA256 index/JS/CSS совпали,
backend health RC `2d12c15b7084b1cb09ba1ff892f185b13afabbc2` сохранён, core **7/7 healthy**.
Production browser **12/12 PASS**, 1280/390 px: отступ 28 px, счётчик 15→10 после
просмотра пяти пунктов, read-all убирает badge, список в границах экрана,
ссылка на центр, single/all read из центра обновляют колокольчик.
Все notification GET/POST в этой UI-проверке подменены локальным ответом в
браузере: **16 mock POST**, **0 HTTP write attempts в production**.
Реальные уведомления/прочитанность пользователя не менялись. Visual QA PASS.

## Публикация и восстановление

Frontend-only, UTC `2026-10-16T08:41:00.461238+00:00`, без простоя. Backend/workers/DB/proxy
сохранили container IDs и состояние. Новые assets скопированы, index заменён
атомарно; **37 прежних assets** сохранены.
Перед заменой архив frontend volume **44 файлов** сохранён EFS off-host
и LUKS mirror, SHA256 сверены. Архив распакован, размеры/хеши восстановленных
файлов совпали. Отдельный DPAPI-носитель ключа на F: проверен test-passphrase.
Владелец Иван, хранение 90 дней без автоудаления. SHA256 архива
`3edc41f9d09c9a9eae24896fe9851374989f13ac6fcc5eeda850febfa220c85e`.

Защищённые source/configs/archive/proofs/screenshots: `I:\AYS Connect\TaskPatch\notification-badge-release-20261016T083836Z`.
Frontend image `sha256:579418459ce264e518405993ba4241ac6cfd186c44141a405b3e4cb3c0c08a6d`.
Backend image сохранён `sha256:6ae6f09650ddf9265caeb3d6877a62ea3dfd3bc0134cfc88cf681d21d51c195a`.
Operational wrappers и frontend metadata согласованы с новой версией;
backend RC, БД, миграции, API и права сохранены. Telegram/receiver выключены.
Три отложенных Telegram source-файла не вошли в Git; секреты, архивы и
пользовательские данные не добавлялись в репозиторий. Статус **DEPLOYED_ACCEPTED**.
