# Выпуск PR #3 — 13 октября 2026

**Production: PASS.** Пользователь явно разрешил развёртывание PR #3.
Runtime RC `d6b2a8126018856377064d6865b784837f05fb6a` опубликован на https://ays-connect.ru/ и https://www.ays-connect.ru/.
Финальный коммит отчёта и тестов не меняет runtime-код опубликованного RC.

## Что опубликовано

Патч задач с опубликованным фирменным дизайном, светлой/тёмной темами,
историей обновлений, компактным реестром объектов и текущей карточкой задачи.
Убраны сервисные заявки из меню, карточки объекта и создания новых обращений;
прямой `/requests/new` предлагает задачу, API создания возвращает 403.
Исторические заявки, комментарии и вложения сохранены.
Ответственное подразделение, пять приоритетов, проектные сроки, несколько
наблюдателей, упоминания и corporate Telegram API входят в runtime.
Исходный worktree дизайна не изменён.

## Сборки и проверки

- Backend/init/шесть workers: `sha256:985d3d986ecd413de5724783e05031568fedba9dd2683050084440d4bcebf0f0`.
- Frontend: `sha256:db6007e530f2eeb350edfe119df5cf62d4ec3fc62b3c189a09353535c7d0ef3a`.
- Fresh production snapshot: `2026-10-13T12:30:46.348909+00:00`.
- Штатный init копии: пять additive migrations, 112 → 117; check/drift/повторный план PASS.
- Исходные 201 таблица сохранены по прежним колонкам и UUID; users/roles/grants не изменены.
- Полный PostgreSQL gate: **672/672 PASS**, parallel=3, точный RC, штатные throttles.
- Совмещённый UI: **11/11 PASS**, desktop 1280 и mobile 390;
  5 проверок дизайна/удалённых точек заявок и 6 на отдельной synthetic DB `pr3_ui`.
- Browser launcher `channel=chromium` дал `spawn UNKNOWN`; явный установленный
  headless-shell-1234 прошёл. Неудачный запуск не считается PASS.
- Реальные scoped personas: 12 historical task detail и 12 collection checks PASS;
  запрет новой заявки проверен даже для owner. Все 50 импортированных объектов доступны owner.
- Live HTTPS: **12/12 HTTP 200**, оба домена, точный index SHA и version RC.
- Live UI под действующим owner: старые задачи, темы, история обновлений,
  отсутствие заявок, прямой старый маршрут и mobile PASS; заблокированы HTTP writes,
  **0 writes**. JWT access создан без login/RefreshToken DB-записей и использован только в памяти.
- Backend и шесть workers: **7/7 healthy**, один pinned image/version.
- После workers неизменны 10 таблиц пользователей, People, прав и импортированной оргструктуры;
  **62 pending location.* сохранены полностью**, включая payload/UUID/status.

## Актуальная защищённая точка

Frozen UTC: **2026-10-13T12:43:28.918354+00:00**. Запись и ingress закрыты; clients=0,
inflight=0, prepared transactions=0. DB/media/frontend: EFS off-host,
LUKS server mirror, совпадающие SHA256. Восстановление именно off-host файлов:
**202 таблицы, media и frontend PASS** до открытия ingress.
Отдельное 8 GiB LUKS-хранилище, ключ восстановлен из отдельного DPAPI носителя
и проверен `cryptsetup --test-passphrase`; plaintext key-файлов нет.
Владелец восстановления — Иван, хранение 90 дней; автоматическое удаление не добавлено.

| Файл | SHA256 |
|---|---|
| database.dump | `adad73fdf3804bb0c4f59a7194cfc6ef87981cfeffb43ec0a267997bea493eb3` |
| media.tar.gz | `740d336fb437270b82d742c0c2bf348156b4eb1eeff4c19773703aef9003a503` |
| frontend.tar.gz | `afe44e6d2ad42d0ec6b84e89fc02ad8a94679116e563963ce79e1811882ef68c` |

Evidence: `I:\AYS Connect\TaskPatch\PR3-release-20261013T121532Z`.
Серверный mirror: `/home/ivan/ays-pr3-release-d6b2a8126018/encrypted-rehearsal/mounted/restore-volumes/ays-pr3-copy-20261013T123029Z/frozen-rollback-20261013T124303Z`.
Резервные config/inspect/DB/media/ключи находятся только в защищённом хранилище,
не в Git. Предыдущие hashed frontend assets сохранены для уже открытых страниц.

Успешное окно: **77.532 с**. Предыдущее переключение автоматически
вернуло прежний код за **81.672 с**: APIClient не учитывал production HTTPS;
probe исправлен и отдельно проверен на production-конфигурации до повтора.
Миграции при возврате не понижались; повторный init имел пустой план.
Суммарный закрытый ingress в двух переключениях — около **159 с**, меньше 15 минут.
Перед вторым переключением снята новая точка после возобновления записи.

Первый полный server gate остановился из-за заполнения старого общего 2 GiB
защищённого filesystem. Его failed derived cluster удалён только после остановки
и проверки owned путей; snapshots и чужие копии не удалялись. Периодический backup
возобновлён и успешно завершён до переключения. Новый полный gate прошёл на отдельном
8 GiB filesystem, без изменения production storage и без удаления backup history.

## Границы и дальнейшая настройка

Импортированные 21 юрлицо, 50 новых объектов и 5 организационных единиц сохранены.
Не создавались сотрудники, позиции, руководители или права. Все 5 подразделений
пока без manager_position; 4 старые задачи без responsible_department.
**Создание задач по новым правилам требует реального People-руководителя**,
а передача старых задач в работу — явного административного заполнения подразделения.
Автоматически назначать руководителей по именам из справочника нельзя.
Templates без department — 0; projects без deadline — 0.

**Постоянная Telegram-доставка выключена**: `NOTIFICATIONS_TELEGRAM_ENABLED=0`,
`TELEGRAM_BOT_SERVICE_ENABLED=0`, transport=pull. Ключи и service credentials не выдавались,
исторический backlog не запускался на внешнюю отправку. Прежние два сообщения через
временный harness — PASS transport, не подключённый постоянный bot adapter.
Для включения нужны отдельная настройка adapter/credential/cutoff и HTTPS acceptance.

После открытия public ingress возможны новые writes: **blind restore запрещён**.
Сначала закрыть запись, сохранить актуальный tail DB/media/Audit/Outbox и согласовать
совместимое восстановление. Не выполнять destructive migration downgrade.

## Уточнение аналитики — 14.10.2026, локально

По запросу владельца из production performance UI удалены «Решено заявок»,
«SLA решения» и «Backlog заявок». Сохранены завершённые задачи, соблюдение сроков,
активная нагрузка, просрочки и переносы сроков. Сетка сводки адаптирована под
четыре карточки, переносы занимают полную ширину; пояснение больше не упоминает
заявителя. Backend-метрики и история не удалялись. Нового deployment/commit/push
не выполнялось; Telegram остаётся отложен до доступа к серверу.

Проверка: TypeScript (`tsc`) и production-сборка Vite PASS, `git diff --check`
PASS. В `frontend/src` больше нет ссылок на три скрытые метрики.
