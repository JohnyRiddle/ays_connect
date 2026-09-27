# People + Projects + iiko + Cards — интегрированный release candidate

Дата проверки: 27.09.2026. Локальная база: commit
`8d9fc81de45e7ecb0049dcaf3f47e2f7ac157e22`, изолированная ветка
`codex/integrated-release`, checkout `AYS Connect integrated release`. Commit и push не
выполнялись.

## Read-only inventory production

Production прочитан по существующему SSH-доступу без изменения файлов и сервисов.
Контур: `/opt/ays-connect`, Compose project `ays-connect-production`. На момент
инвентаризации сервисы были healthy. Маркеры версии:

- базовый deployment: `DEPLOYED_COMMIT=98c23a7+backup-hotfix`;
- iiko: `food-limit-20260910`, backend image
  `ays-connect-iiko-backend:food-limit-20260910`, digest начинается с
  `sha256:0e992902`;
- Cards dashboard и вкладки сезонов установлены как серверные изменения;
- iiko Git-origin найден в `origin/codex/iiko-integration-checkpoint`, commit
  `26d3907aa8116ed4b67c7b6035711f8247d21425`;
- production source не является Git checkout. После iiko checkpoint на сервере есть
  десять изменённых и восемнадцать добавленных файлов, включая Cards, Compose overlay
  и deployment markers.

С сервера скопированы только 56 явно перечисленных исходников, документация,
Compose/template-файлы и deployment markers. `.env`, credentials, БД, media и логи
не читались и не копировались. Полный SHA-256 allowlist:
[PRODUCTION_INVENTORY_2026_09_27.sha256](PRODUCTION_INVENTORY_2026_09_27.sha256).

Production `backend/requirements.txt`, `frontend/package.json`,
`frontend/package-lock.json`, `deployment/backup.sh` и базовый
`docker-compose.prod.yml` содержательно совпадают с release base; наблюдавшиеся
различия хешей общих текстовых файлов объяснялись окончаниями строк. Локальные
незакоммиченные Cards-файлы в checkout `AYS Connect` совпали с production byte-for-byte.
Этот checkout не изменялся.

Фактически применённые release-релевантные migration cutoffs:

- `accounts.0002_initial`;
- `employees.0012_seed_profile_permissions`;
- `work_tasks.0003_alter_task_source_type_taskrecurrencerule_and_more`;
- `events.0002_outboxevent_failed_at_outboxevent_last_error_code_and_more`;
- `iiko.0007_cardcreation_topup_amount_and_more`.

## Состав кандидата

- весь checkpoint People + Projects `8d9fc81`;
- production-exact iiko backend, migrations `0001..0007`, API, UI, tests и
  non-secret templates;
- production-exact Cards dashboard, сезоны 25–26/2027 и пять изображений;
- backup hotfix `deployment/backup.sh`;
- объединённые Django apps/routes/settings, RBAC catalog, frontend router/navigation;
- `docker-compose.iiko.yml` без pin старого iiko image, чтобы backend и workers
  запускались из одного integrated image;
- исправленный synthetic staging startup: миграции/collectstatic завершаются до
  запуска backend и workers.

Не включены посторонние Knowledge/Learning/demo-изменения из iiko Git-ветки: их не
было в production allowlist. `seed_permissions` использует `update_or_create` только
для каталога прав и не назначает новые роли существующим пользователям.

## Итоговый gate

| Проверка | Результат |
|---|---|
| Полный backend, PostgreSQL | **546/546 PASS**, 205.929s |
| iiko backend regression, без реальной интеграции | **102/102 PASS** |
| Django `check`; migration drift | PASS; `makemigrations --check --dry-run` — no changes |
| Frontend production build | PASS, 1811 modules; Cards assets включены |
| People HTTP API / browser | **73/73 PASS**, **5/5 PASS** |
| Projects HTTP API / browser | **37/37 PASS**, **2/2 PASS** |
| Cards + iiko integrated browser | **1/1 PASS**, оба сезона и iiko shell; внешних запросов нет |
| Production-cutoff upgrade | PASS: 24 targets, 13 новых миграций, repeat plan пуст |
| Synthetic backup/restore | PASS: 196 таблиц, 174 строки, 2 media; DB guard после restore PASS |
| People Notification Core worker | PASS: 5 причин, In-App+Email, без дублей |
| Projects milestone worker | PASS: 1 notice/outbox/notification, 2 channels, repeat scan 0 |

Upgrade harness сохраняет синтетические People, Work и iiko строки, проверяет
`auth_version`, backfill/SQL guard Work acceptance, появление Projects и его SQL
guards. iiko API tests используют mocks; staging не содержит production credentials.

## Deployment runbook

1. Зафиксировать target host, текущие image IDs/digests, deployment markers,
   `docker compose ps`, health, `showmigrations` и хеши Compose/config templates.
   Остановиться при неизвестном server drift; файлы на месте не перезаписывать.
2. Собрать backend/frontend/worker images только из будущего неизменяемого integrated
   checkpoint. Выполнить `docker compose config`, `check`, migration plan и проверить,
   что init/seed не входят в автоматический startup. `seed_permissions` при необходимости
   запускается отдельно и не выдаёт grants.
3. До maintenance проверить свободное место на основном и backup-диске и согласованный
   off-host target. Включить maintenance, остановить backend write traffic и все workers.
4. Создать `pg_dump --format=custom` и media tar штатным `deployment/backup.sh`, сохранить
   SHA-256. Скопировать в заранее согласованное доверенное off-host место, повторно
   проверить хеши и выполнить isolated restore. В restore-контуре отключить SMTP,
   Telegram, iiko, cron и workers и не передавать production credentials.
5. Только после успешного restore применить migration plan. Ожидаемая дельта:
   `accounts.0003`, `employees.0013..0015`, `work_tasks.0004`, `projects.0001..0008`;
   iiko остаётся на `0007`. Затем одновременно переключить backend и workers на один
   integrated image, frontend — на integrated assets. Старые backend/workers не
   запускать с новой схемой.
6. Проверить health, release SHA/image digests, `migrate --check`, логи, очередь Outbox
   и отсутствие failed/repeated deliveries. Затем выполнить read-only smoke People,
   JWT, Projects, Work, iiko config availability, Cards seasons и защищённую выдачу
   файлов. Write smoke допускается только на маркированных synthetic объектах и
   существующей тестовой учётной записи, без реальной отправки iiko/уведомлений.
7. Снять maintenance только после обязательного smoke. Сохранить предыдущие images и
   backup до отдельного решения о retention.

Условия остановки: неожиданный migration plan, неизвестный drift, отсутствие полного
backup/off-host checksum/restore, нехватка места, выдача новых grants, unhealthy
service, ошибки Outbox/workers, scope/auth/file regression или обращение smoke к
реальной интеграции.

До возобновления записей rollback выполняется по runbook: остановить все новые
компоненты, оценить применённые миграции, вернуть прежние images и при необходимости
восстановить БД/media из текущего pre-deploy backup. Одного rollback кода недостаточно,
если миграции изменили данные/ограничения или новые компоненты уже записали данные в
новую схему. После возобновления пользовательских записей старую БД нельзя
восстанавливать без отдельного решения по сохранению новых реальных данных.

## Off-host варианты и blockers

Read-only inventory не обнаружил настроенных NFS/CIFS mounts, rclone target или remote
backup job. `/dev/sdb1` — отдельный диск того же production host, поэтому он остаётся
локальным restore source и не считается off-host.

Доступный в существующей инфраструктуре кандидат — текущая доверенная рабочая станция
с локальным OneDrive-каталогом: передача может выполняться клиентским `scp`, затем
локальный SHA-256 и isolated restore. До явного выбора это только кандидат; реальные
данные туда не передавались. Другого подтверждённого off-host target инвентаризация не
нашла.

Production deployment остаётся **BLOCKED** до двух условий: создан immutable integrated
checkpoint и выбран off-host target, куда успешно скопирован и изолированно восстановлен
актуальный pre-deploy backup. Forgotten-password и движок зависимостей Work Task остаются
вне релиза.
