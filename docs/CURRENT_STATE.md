## 13.10.2026 — production импорт ЦФО выполнен

По поручению «Приступай», после согласования новых UUID и timezone офиса,
созданы 21 LegalEntity, 5 OrgUnit (4 department, 1 company), 50 Location.
Новые UUID v4/FK — PASS; 54 связи с юрлицами, один intentional null, 5 исключений.
201-table protected restore, rollback probe и replay без дублей PASS.
Production Audit/Outbox +76/+76; исходные Location/Tasks/People/grants сохранены.
Owner API 76/76, scoped deny 50/50, HTTPS health 6/6 PASS.
Objects в preparation; реальные руководители/positions/roles не назначены,
старые задачи не перепривязывались. Приложение/PR 3 не развёртывались.
[Evidence и границы](CFO_IMPORT_ACCEPTANCE.md).

## 13.10.2026 — подготовка импорта ЦФО

Подготовлен защищённый review пакет: 60 исходных строк, 55 включены
(50 Location, 2 OrgUnit, 3 организационные службы), 5 пользовательских исключений;
54 связи с 21 юрлицом, один intentional null. Source-preservation, cross references,
user corrections, XLSX counts/visual QA и ZIP/EFS проверки PASS.
Подготовка согласована пользователем 13.10.2026; фиксируется отдельным commit.
Формат custom review-only, не fixture/HTTP body; UUID руководителей/позиций
не заполнены, production apply не выполнялся. [Контракт и ограничения](CFO_IMPORT_PREPARATION.md).

## 13.10.2026 — PR 3 production copy и Telegram test

Backend RC 98dfafa, [draft PR 3](https://github.com/JohnyRiddle/ays_connect/pull/3).
Свежий snapshot 09:56:06 UTC: штатный init пяти migrations 112→117 и
сохранность всех 201 исходной таблицы/реальных grants PASS; 12/12 historical
scope detail, 38/38 focused PostgreSQL PASS. Полный серверный 672 repeat не завершён
из-за ресурса filesystem; прежний synthetic 672/672 и browser 6/6 остаются отдельными gates.
Два реальных сообщения @AYS_ai_expert_bot → @ivan_ays (15024/15025), claim/begin/ack,
роли-дубли, одноразовая привязка и revoke до begin PASS; получатель подтвердил.
Это copy API harness + transport, постоянный HTTPS adapter пока NOT VERIFIED.
Frozen 10:27:59 UTC DB/media/frontend: EFS/LUKS, SHA и off-host restore 201 таблицы PASS.
Maintenance суммарно 66.938 с; прежние images/backup возобновлены, HTTPS 6/6 и health PASS.
Merge/deployment не выполнялись. До выпуска: 0 departments/4 old tasks без department,
окончательный опубликованный дизайн, постоянный bot adapter/staging, финальный RC и
актуальная frozen точка. [Полное evidence](TASK_PATCH_REHEARSAL.md).

## 13.10.2026 — патч задач и API корпоративного Telegram-бота (review)

Изолированная ветка `codex/task-telegram-patch`, base `origin/main` 62c61ed;
runtime совпадает с 713be6b, обновление базы ветки касается только документов
регистрации. Новые обращения — Work Tasks; Request create UI/API закрыт,
история не переносится и не удаляется. Добавлены department/head routing,
object-scoped executor choices, пять приоритетов с calendar deadlines,
project deadline inheritance без active priority, watchers/UUID mentions и
service-only corporate Telegram claim/begin/ack/fail. Новые проектные задачи
наследуют объект проекта; membership/primary_location не создают grants.

Только пять additive migrations; old department null требует административного
заполнения задач и templates. При передаче в работу проверяется текущий активный
руководитель. Реальные grants/UUID/история и pending location.* не менялись.

Проверки: 672/672 backend PostgreSQL, 38 новых сценариев включая races/upgrade,
6/6 browser desktop/mobile с реальным isolated API, TypeScript/Vite, check/drift,
diff --check и export 8 OpenAPI routes PASS. Полный evidence/границы:
[TASK_PATCH_ACCEPTANCE.md](TASK_PATCH_ACCEPTANCE.md). Контракт:
[telegram-bot/README.md](telegram-bot/README.md), инструкция:
[TASK_PATCH_USER_GUIDE.md](TASK_PATCH_USER_GUIDE.md), выпуск/restore:
[TASK_PATCH_RELEASE.md](TASK_PATCH_RELEASE.md).

Последующие production-copy/frozen/real transport gates описаны в
[TASK_PATCH_REHEARSAL.md](TASK_PATCH_REHEARSAL.md); постоянный HTTPS adapter NOT VERIFIED. Before release интегрировать с
финальным commit опубликованного дизайна и проверить exact RC. Исходные dirty-файлы
других checkout не включены. Commit/push и черновой PR разрешены пользователем 13.10.2026; merge/deployment
требуют отдельного разрешения именно этого патча.

## 12.10.2026 — Registration production release PASS

Runtime **713be6b755950fcce5f5bf22d9fc05743c8f0053** (AssignmentTarget integration included). Synthetic acceptance
**634/634 PostgreSQL, targeted 61/61, desktop/mobile 6/6 PASS**. Final restored
production rehearsal: snapshot **2026-10-12T12:53:30.278133+00:00**, original 198 tables preserved,
full init six migrations 106→112, API 40/40, immutable frontend browser 6/6 (23.7s).
Frozen rollback snapshot **2026-10-12T13:18:22.743916+00:00**: protected off-host DB/media restored and full
copy init PASS before production init. Live acceptance PASS: owner normal UI approval,
scoped/denied API, invitation security, copied UI invite and both Work selectors.
Two test User/Employee pairs terminated, assignments revoked, old access/refresh/new
login 401; two test objects closed/archived, history retained. No real grants changed.
Production backend + six workers healthy; registered consumers processed 25 new state
events, zero new registration mail/external attempts. Public HTTPS/live/ready PASS on
both domains. Ingress closed **1692.880 s**; maintenance **1700.693 s**.
Existing superusers approve first release; ordinary-manager setup is optional and
was not backfilled. Current source has six original location events (previous five
plus 12 October creation), retained pending; unhandled lifecycle events retained too.
Deployment PASS. Merge is recorded by [PR #2](https://github.com/JohnyRiddle/ays_connect/pull/2)
after the release evidence commit; no second init/deployment is required.
[Release evidence, images, limits and recovery](REGISTRATION_RELEASE.md).

Earlier sections below are historical evidence for their explicitly named RCs.

## 12.10.2026 — Registration fresh restored production rehearsal PASS

Runtime RC f3305408cc85d6d95db74706742499ceadb6c820 published in draft PR #2.
Fresh online snapshot observed 11:40:14.426 UTC / 18:40:14.426 Novosibirsk; original
restore 198/198 tables, full init six migrations 106→112, old users/RolePermission/
EmployeeRole unchanged; no assignment to existing users. Repeat plan/check/drift PASS.
Actual copy API 38/38, browser 6/6 (18.3s) without SMTP. Protected EFS off-host/LUKS
volumes, egress blocked; copy stopped, production unchanged/no downtime.
One active registration object; 3 existing superuser candidates can approve/delegate.
No active scoped non-superuser manager setup; no real grants changed to pass.
Production readiness CONDITIONAL: current drift/setup, pinned frontend, separate
consistent rollback/write-window/live smoke gates. Snapshot is online, not frozen
DB/media rollback point. [Exact evidence/limitations](REGISTRATION_REHEARSAL.md).

## 12.10.2026 — Registration requirements: без подтверждения email и писем

Self submit сразу pending, рабочий доступ после approval; invite submit сразу
approved в атомарной транзакции. Email обязателен/normalized/unique, mailbox ownership
не проверяется. Mail events не создаются; старые jobs terminal disabled, old confirmation
requests отменяются с Audit/Outbox, legacy activation закрыт. Шесть additions.
No-SMTP API/upgrade 42/42 PASS (92.068s), browser 6/6 PASS (13.5s), build/check/drift PASS.
PostgreSQL полный regression **627/627 PASS, 408.376s**. Реальная restored DB/grants и scoped approvers/delegation
остаются обязательными. SMTP исключён из gates; production регистрации NOT PERFORMED.
[Матрица](REGISTRATION_ACCEPTANCE.md), [контракт/release](REGISTRATION_IMPLEMENTATION.md),
[инструкция](REGISTRATION_USER_GUIDE.md). Изолированная codex/registration; исходные
13 dirty-файлов и Objects CRLF-only views.py сохранены.

## 09.10.2026 — Objects production release PASS; PR #1

Storage gate **PASS для действующего backup/restore контура**: 24 исходных файла скопированы на LUKS2 с полным совпадением path/size/SHA-256/UID/GID/mode/mtime; guard отказал на обычном ext4 (exit 78, ноль новых файлов), missing bind source — exit 125 без fallback. Новый periodic backup 12:33:16 UTC корректен, история сохранена; retention отключён. Исходные 24 файла остаются отдельно на незашифрованном `ays-connect-production_backup_data`: **не вся история зашифрована**, удаление не выполнялось. Persistent crypttab/fstab manual unlock/noauto и Compose bind create_host_path=false проверены; reboot не выполнялся. Отдельная DPAPI key copy восстановлена и проверена. Guard и обязательный override опубликованы в deployment; source/backend/frontend runtime и схема относительно RC220ffac не изменены.

Новая frozen rollback точка **09.10.2026 12:51:50.390359 UTC**: исходная production версия main64f85fa, 101 migrations; Location/Facility/Zone/Company/Region/Cluster/LegalEntity/OrgUnit отдельно 0, Users 5/Employees 4 с явно разрешённой test persona, RolePermission 125/EmployeeRole 1. **O0 PASS / mapping-transfer N/A только этого snapshot**, ограничения encoded/name-only скана сохранены. EFS off-host DB/media SHA и restore именно из этих файлов PASS; дополнительная age copy расшифрована отдельно защищённым ключом и дала те же SHA. Полный init копии и production — PASS: ровно access_control 0003 + organizations 0004–0007, migrate/seed_permissions/collectstatic/chown, 101→106, повторный plan [], check/drift PASS, реальные grants сохранены. Copy 196/1981→198/2004, 192 старых tables unchanged, четыре ожидаемых catalog/migration delta, catalog label renames 0. Дополнительный online rehearsal API **32/32, 17.762s**; полный 585 и browser 6 не повторены, runtime не менялся.

Live SSH-only smoke **PASS в согласованном контексте**: owner normal UI create, намеренно прерванный первый ответ только smoke relay, идентичный UI replay с тем же Idempotency-Key/payload — upstream 201→200, тот же UUID, один idempotency record. Non-staff/non-superuser persona: denied detail 404/create 403/list count 0/lookups без скрытых IDs; location-scoped view/manage_zones — list count 1/detail 200/zone create 201/zone count 1/stale repeat 409, root create вне контекста/edit 403. Related counts People/Work/Requests/Projects/participation 0, реальные People/Tasks/Project detail 404; Requests collection 200 с count 0, это scoped empty result, не 403. Legacy write persona 403, smoke admin ingress 403; live owner legacy 405/Admin write-form **не проверялись**, прежние code/copy проверки сохраняются. Positive root create через LegalEntity **NOT PERFORMED/N/A без разрешённого контекста**; scoped positive create здесь — зона в явно разрешённом test parent, никаких искусственных LE/OrgUnit.

Test scope отозван; persona User 6 / Employee fa09c72e-5a01-49f4-a7da-8e32856ea903 штатно inactive/terminated, test role inactive, assignments 0, session revocation audited. Fresh valid access до cleanup 200, тот же access после 401, refresh 401/new login 401; исходные live tokens также проверены по public HTTPS — 401/401/401. История не удалена. Root `4c2f1c70-3ab6-42bc-90e0-5e056109c257` и zone `a8e67240-e071-4a14-bd91-1c860912263e` закрыты/архивированы через ObjectService с policy checks оператором по SSH; **не заявляется UI/API cleanup**. Ровно 2 Location, 1 idempotency, 5 Audit и 5 Outbox; новая зона под архивным parent отвергнута domain ValidationError без новых rows/events. Ни ответственных, ни бизнес-связей, ни operating status не создавали.

Production открыт **13:06:33.407 UTC (20:06:33.407 Asia/Novosibirsk)**. Maintenance window 12:51:11.520→13:06:33.407 UTC — **921.887s / 15m21.887s**; точный момент остановки proxy отдельно не записан, это измеренное окно maintenance, а не отдельный таймер proxy. Backend/6 workers healthy, HTTPS/live/ready двух доменов **6/6 HTTP 200**, frontend volume 8/8 files exact immutable artifact. Workers запущены 13:05:16.819 UTC: с этого момента возможны реальные новые writes; **blind restore rollback point запрещён**. Outbox failed=0, пять location.* pending/attempts=0/unique event IDs: consumers для них не зарегистрированы, **доставка не проверена и не объявляется PASS**; NotificationDeliveryAttempt=0/test employee deliveries=0. Backup running encrypted/retention disabled, owned smoke/copy helpers/tunnel stopped, encrypted volumes/evidence сохранены. Исходные 13 dirty-файлов и CRLF-only views.py побайтово сохранены.

**Code/synthetic acceptance PASS; snapshot O0/upgrade PASS; deployment PASS для согласованного pilot scope.** Release runtime RC `220ffac89568a0e7b2aa493a4b599e0aa1946772`; backend/6 workers 416/416 source files exact RC. Фактический merge SHA фиксируется в GitHub PR #1; merge выполняется после acceptance и не запускает повторный init/deployment. Recovery owner Иван, хранение 90 дней (fresh point минимум до **07.01.2027 12:51:50 UTC**), удаление только его решением. Unencrypted retained source, portable/off-device DPAPI recovery, full-disk BitLocker/free-space remanence, populated attachment compatibility, encoded/name-only references и неподтверждённые live сценарии остаются явными ограничениями. [Полные SHA, команды и startup/rollback](OBJECTS_RELEASE_READINESS.md).

### Исторические записи до storage cutover и выпуска

## 09.10.2026 — release STOP до maintenance; temporary persona закрыта

Повторная фактическая storage проверка обнаружила незакрытый обязательный gate: действующий `ays-connect-production_backup_data`, 24 файла / 8124 KiB, находится на `/dev/sdb1 ext4`, без подтверждённого crypt-слоя. EFS off-host/LUKS rehearsal storage не защищает этот действующий volume. Перед GO требуется проверенное переключение всего periodic backup storage на encrypted mount с сохранением bytes/UID/GID/modes, возобновлением без запуска retention и отказом записи при отсутствии encrypted mount. Пользовательский downtime **0 секунд**; production init, merge, deployment и новый release backup не выполнялись. Прежняя версия production сохранена.

Temporary production persona User 6 / Employee fa09c72e-5a01-49f4-a7da-8e32856ea903 штатно закрыта после STOP: active assignments 0, User inactive, Employee terminated/inactive; audited session revocation, фактический access до закрытия 200, тот же access после 401, refresh 401, новый login 401. Реальные User values не менялись, audit/rows сохранены. Live denied/scoped Objects acceptance **NOT PERFORMED**, прежний rehearsal PASS относится только к копии; этот cleanup PASS не является разрешением пропуска live gate. Для следующей попытки проверить статус persona и свежий baseline заново; не использовать уже отозванные credentials.

Production после STOP: 11 running containers, backend и 6 workers healthy, backup running/unpaused, оба HTTPS домена и live/ready — 6/6 HTTP 200. Исходные dirty bytes сохранены. Snapshot O0/upgrade PASS и legacy N/A остаются ограничены snapshot 09:49 UTC; production readiness **CONDITIONAL**, deployment **NOT PERFORMED**. Разрешение release сохраняется после устранения STOP, повторное разрешение предусмотренных шагов не требуется.

## 09.10.2026 — Objects RC220ffac: fresh backup / off-host restore / full init PASS

### 09.10.2026 — encrypted preflight и временная live persona подготовлены

Разрешены one test User/Employee и минимальные audited scope assignments с обязательным revoke/terminate/token/session denial, без изменения реальных grants. Production persona User 6 / Employee fa09c72e-5a01-49f4-a7da-8e32856ea903 создана non-staff/non-superuser, пока 0 grants; baseline теперь Users 5/Employees 4. Owner штатно вошёл на SSH-only localhost:13041. Новый I:\AYS Connect EFS off-host destination, DPAPI key copies на отдельном физическом F: с фактическим age/LUKS recovery check, server LUKS2 и relocation retained backup/restore volumes с SHA/UID/GID/mode сохранением подготовлены. BitLocker/off-device recovery/free-space remanence не заявлены PASS. Persona scenario/credential revocation rehearsal PASS только copy; production rights/cleanup ещё NOT PERFORMED. Positive scoped create — zone в разрешённом smoke parent; root LegalEntity scoped-create N/A без разрешённого контекста. Fresh rollback point/restore/init/live tests впереди; readiness CONDITIONAL, deployment на момент preflight NOT PERFORMED. [Evidence, scope и recovery constraints](OBJECTS_RELEASE_READINESS.md).


### 09.10.2026 — разрешённый release: STOP до maintenance

Merge/deployment не начаты: обязательные gates не закрыты. Актуальный production: Users 4/Employees 3 против snapshot 3/2; Role/RolePermission/EmployeeRole fingerprints прежние (1/125/1), source runtime 407/407 × 7 containers прежний, migrations 101, восемь целевых справочников отдельно 0. Active non-superuser persona отсутствует; scoped/denied production acceptance не заменяется owner superuser или anonymous 401. Шифрование всех raw/restore storage и независимая key custody не доказаны. Штатная original-origin сессия ivan@ays-connect.ru есть, SSH-only origin login ещё NOT VERIFIED. Pinned images/override PASS; прежние 13 containers/images и HTTPS 6/6 200 сохранены; downtime этой попытки 0. Release/merge SHA нет, RC220ffac / PR#1 draft остаются. Recovery owner Иван, retention 90 дней/delete только им. Разрешение предусмотренного runbook цикла сохраняется после устранения блокеров; PASS непроверенным сценариям не присваивается. [Точные STOP evidence и условия](OBJECTS_RELEASE_READINESS.md).


### 09.10.2026 — финальный release package RC 220ffac

Exact-RC frontend image и backend/worker/init override подготовлены без переключения production; prod-flavoured bundle через SSH-only isolated ingress — browser 6/6 PASS. Runtime/schema неизменны относительно checkpoint 73a8092; full regression не повторён. Snapshot O0/upgrade PASS относится только к 09:49 UTC, legacy mapping/перенос N/A только snapshot. Recovery owner — пользователь; retention 90 дней, удаление только им; P1/office/Asia/Novosibirsk/один object+zone+archive согласованы. Отдельная age encrypted copy существующего backup проверена, но raw backup/volumes encryption и независимая key custody не доказаны. Нет active denied/scoped production persona: требуется существующая persona или явное принятие ограничения. Новый production backup/init/smoke/deployment, commit/push/merge не выполнялись. Production readiness CONDITIONAL. GO/STOP, точные digests/override, разрешённый delta smoke и rollback с сохранением новых данных: [OBJECTS_RELEASE_READINESS.md](OBJECTS_RELEASE_READINESS.md).


RC `220ffac89568a0e7b2aa493a4b599e0aa1946772`; runtime/schema относительно 73a8092 unchanged, полный 585 gate не повторялся. Свежая разрешённая maintenance репетиция: source 101/0/0, 407/407 backend и каждого из шести workers совпали с main64f85fa; Location/Facility/Zone и остальные пять справочников=0, grants проверены заново. **O0 PASS / legacy mapping-transfer N/A только для frozen snapshot 09:49 UTC**, DB SHA `df1943c4e0286cb1d0cfe55ade14ce636187138134f137d1c0d1e9762c777504`.

Согласованные DB/media backup, защищённая off-host копия и независимый restore **PASS**. Proxy stopped **193.697s**, maintenance с финальными checks **201.602s**. Прежние IDs/images/services возобновлены **до** isolated rehearsal; оба HTTPS домена/live/ready=200, backend/шесть workers healthy, backup timer unpaused без retention, старые backups unchanged. Production остался на прежней схеме 101 migrations и прежних accounts/grants.

**Полный actual RC init copy PASS**: migrate/seed_permissions/collectstatic/chown; ожидаемые пять additions, repeat plan [], check/drift PASS. 196/1950→198/1973; 192 old tables unchanged, только четыре служебных delta; реальные RBAC/users/business data preserved, independent original restore/media fingerprints PASS. API **32/32,19.078s**, browser **6/6,29.5s**; после тестов изменились только три test number counters в копии. Новые volumes сохранены, test containers/tunnels остановлены. Runtime/test не менялись.

**Production readiness CONDITIONAL, production write-smoke/deployment NOT PERFORMED**. Остаются отдельное release разрешение, immutable frontend/production image override, test-only ingress/personas, свежая drift/rollback точка после resume writes, off-host retention/at-rest/recovery policy и actual production smoke/worker acceptance. [Точные UTC/SHA/команды/ограничения и отдельный release plan](OBJECTS_RELEASE_READINESS.md). Commit/push/merge/production init в этой задаче не выполнялись. Исходные 13 dirty-файлов и CRLF-only views.py сохранены. Нижние записи — исторические snapshot evidence.

## 09.10.2026 — Objects release candidate; O0 snapshot и restored upgrade PASS

Предоставленный SSH identity дал read-only доступ к работающему документированному production. **O0 DATA BLOCKED снят для актуального snapshot**: PostgreSQL 17.11, Location/Facility/Zone/Company/Region/Cluster/LegalEntity/OrgUnit=0, migrations 101/0/0. Получение согласованного dump завершено 2026-10-09T06:53:54.581111+00:00; время открытия pg_dump transaction отдельно не записано. PASS ограничен этим snapshot/SHA из readiness report. **Legacy mapping/transfer N/A** по доказанному отсутствию legacy. Runtime backend совпал с main `64f85fa…` по 407/407 нормализованным исходникам. Fresh защищённый DB dump получен вне Git/OneDrive; изолированный contour с новой internal network/volume, без workers/integrations/public ports/production media.

Upgrade **PASS**: пять Objects migrations, baseline 196/1950 → 198/1973, сохранены old business data и grants, check/drift/repeat plan PASS, independent original restore fingerprints PASS. API **32/32** на рабочей restored structure внутри rollback; browser **6/6, 29.9s**. **Code/synthetic acceptance PASS**: runtime checkpoint `73a8092b4b0675daf2f0a6ab11fb8e090226f58c` не менялся; локальный follow-up — две URL waits в browser test и документация. Полный 585 gate не повторялся. Исходные 2 Work/1 Project сохранены; test creation изменил только ожидаемые служебные number counters в копии.

**Production readiness CONDITIONAL / NOT VERIFIED полного выпуска; deployment NOT PERFORMED**: online DB snapshot не заменяет fresh maintenance DB/media/off-host restore. [Полное readiness evidence, версии и следующий шаг](OBJECTS_RELEASE_READINESS.md). Runtime checkpoint `73a8092…` + documentation/browser-test follow-up `docs(objects): record production snapshot upgrade acceptance` подготовлен к разрешённой публикации в draft PR #1. Реальные source passwords/roles/schema не менялись; merge/deployment нет. Предыдущие blocked выводы ниже — история до предоставления identity. Исходные 13 dirty файлов и CRLF-only views.py сохраняются.

## История 09.10.2026 до предоставления identity — O0 DATA BLOCKED

Ветка `codex/objects`, локальный/remote SHA `73a8092b4b0675daf2f0a6ab11fb8e090226f58c`, draft [PR #1](https://github.com/JohnyRiddle/ays_connect/pull/1), base актуального main `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`. Функциональность реализована; code/synthetic acceptance PASS (585/585, Objects 36, inventory 8/8, browser 6/6, build/check/drift и synthetic install/upgrade/restore). 36 source SHA совпали с manifest; код в новой O0 задаче не менялся, gate не повторялся.

Документированный production найден, но повторный SSH, включая существующий deploy-key, отказал (`Permission denied (publickey)`). Актуальный backup не подтверждён; Docker API локально вернул 500, snapshots не обновлялись. **O0 DATA BLOCKED; рабочая upgrade compatibility, реальные mapping, перенос и production readiness — NOT VERIFIED. Production deployment — NOT PERFORMED.** Старые локальные нули не свидетельствуют о production. Подготовлены [release readiness / безопасный план restore / следующий шаг](OBJECTS_RELEASE_READINESS.md) и обновлён [O0 report](OBJECTS_O0_ACCEPTANCE.md). Требуется настроенный разрешённый SSH-доступ и подтверждение актуальности документированного контура, без секретов в чате. Commit/push/merge/deployment в этой задаче не выполнялись; публикация checkpoint была отдельным ранее разрешённым действием. Исходные dirty файлы и CRLF-only views.py сохраняются.

## 08.10.2026 — Objects READY FOR CHECKPOINT; O0 DATA BLOCKED

Функциональность Objects реализована в изолированном worktree `codex/objects` от `64f85fa`: существующий Location UUID, UI create/retry, зоны/ответственные/lifecycle, scopes, Audit/Outbox, связанные People/Work/Requests/Projects. Финальное review всего tracked/untracked diff исправило create без view, скрытые FK в старом API/Admin, restore под архивным предком и потерю скрытых/неизменённых полей UI PATCH; связанные записи и legacy не классифицировались и не переносились.

Synthetic acceptance **PASS** на окончательном коде 08.10.2026: свежий PostgreSQL **585/585** (в том числе Objects **36**, concurrency **4**), inventory **8/8**, browser **6/6**, build/check/drift/Compose/diff PASS; read-only upgrade/restore fingerprints повторно совпали. Схема при review не менялась, append-only install/upgrade evidence 02.10 сохранён. **O0 DATA BLOCKED; реальные mapping, перенос и production readiness — NOT VERIFIED.** Пустые локальные counts не трактуются как production.

[Acceptance и команды](OBJECTS_ACCEPTANCE.md), [точный checkpoint manifest](OBJECTS_CHECKPOINT.md), [O0 evidence](OBJECTS_O0_ACCEPTANCE.md). Все 13 исходных незакоммиченных файлов прежнего checkout на main побайтово сохранены, в checkpoint не входят. Commit/push/merge/deployment не выполнялись.

## 02.10.2026 — Work Task actions UX (local candidate)

В отдельной ветке `codex/work-task-actions` от `origin/main` упрощена шапка карточки Work Task: один следующий переход и доступное меню второстепенных операций. Completion flow показывает передачу на обязательную приёмку, сохраняет результат при ошибке и показывает server-derived blocker обязательного checklist без раскрытия действий пользователям без прав. Synthetic browser gate и затронутые backend/frontend проверки описаны в [WORK_TASK_ACTIONS_UX.md](WORK_TASK_ACTIONS_UX.md). Проверки выполнены в synthetic staging; релизный checkpoint разрешён после завершения gate.
# Текущее состояние AYS Connect

## Projects UX — локальный staging candidate, 02.10.2026

На базе актуального `origin/main` (`d2f91d0`) в отдельной ветке `codex/projects-ux`
перекомпонована страница проекта: компактная шапка, задачи по умолчанию, URL-состояние
фильтров/страницы/вкладок/представлений, server-side фильтрация до пагинации с totals,
этапные группы, split-create, task menus, lazy-loading и адаптивный mobile UI. Боковая
навигация сгруппирована; профиль разделён на read-only `/people/me` и self-service
`/people/me/edit`, доступные через клавиатурное меню аккаунта со штатным logout.

Финальные проверки: frontend production build PASS, Projects + TaskTemplate PostgreSQL **34/34**,
Projects browser acceptance **2/2**, расширенный UX/account browser gate **2/2**. Положительный
browser-сценарий «Из шаблона» использует `task_template.view/use` scope `own` и проверяет
одну Work Task, этап, параметры, приёмку и idempotent repeat без дубля. Desktop и mobile
evidence получены на синтетическом проекте «Запуск сезона». Подробности и
воспроизводимые команды: [PROJECTS_UX.md](PROJECTS_UX.md). Commit/push/deployment и
production-операции не выполнялись.

## Integrated People + Projects + iiko + Cards candidate — 27.09.2026

На базе `8d9fc81` в изолированном checkout `AYS Connect integrated release`, ветка
`codex/integrated-release`, объединены принятые People/Projects и production-exact iiko,
Cards/seasons и backup hotfix. Production inventory выполнен read-only; секреты, БД,
media и data logs не копировались. Полный новый gate: backend **546/546**, iiko
**102/102**, People API/browser **73/73 + 5/5**, Projects **37/37 + 2/2**, Cards/iiko
browser **1/1**, frontend build, production-cutoff upgrade и synthetic backup/restore —
PASS. Staging Compose исправлен: workers ждут окончания миграций. Commit/push не
выполнялись. Deployment заблокирован до immutable checkpoint и проверенного off-host
restore point. Инвентаризация, SHA-256, gate и runbook:
[INTEGRATED_RELEASE_2026_09_27.md](INTEGRATED_RELEASE_2026_09_27.md).

## Финальное ревью People + Projects — 27.09.2026

Полный локальный diff от `f13bfce`, включая новые файлы, проверен в `AYS Connect актуальный` / `codex/projects`. Исправлены lifecycle-валидация ответственных и дат при создании Project stage/milestone, строгий контракт write payload и отзыв Work-уведомлений при потере SQL-доступа к задаче. Финальный PostgreSQL backend **444/444**, Projects **29/29**, затронутый набор **65/65**, API **37/37**, browser **2/2**, оба live notification worker, frontend, check/drift и sensitive scan — PASS. Схема после ранее проверенных clean upgrade/restore не менялась. Подробности: [PEOPLE_PROJECTS_FINAL_REVIEW.md](PEOPLE_PROJECTS_FINAL_REVIEW.md).

## Projects — локальная реализация, 15.09.2026

Ветка `codex/projects` в checkout `C:\Users\riddl\OneDrive\Документы\AYS Connect актуальный`, HEAD `f13bfce` плюс сохранённые незакоммиченные People-изменения. People Acceptance **PASS** на базе до начала Projects; evidence и отдельный product gap forgotten-password приведены ниже. Реализованы Project/PRJ lifecycle, участники, этапы, контрольные точки, связь с единой Work Task, создание из Work/template, SQL scope, Audit/transactional Outbox, Notification Core, API, UI и защищённые документы. Канонических зависимостей Work Task нет; метрика блокирующих зависимостей остаётся отдельным продолжением согласно ТЗ.

Projects локальный Quality Gate на окончательном коде **PASS**: PostgreSQL backend 444/444, Projects staging API 37/37, браузер 2/2, живой Notification worker и repeat без дубля, frontend build, check/drift/migrate, synthetic clean upgrade/restore, diff и sensitive scan. Требование → проверка → результат → конкретный blocker: [PROJECTS_ACCEPTANCE.md](PROJECTS_ACCEPTANCE.md). В первом релизе blocker отсутствует; Work dependency engine и метрика зависимых блокировок остаются отдельным product-продолжением. Production, реальные аккаунты/credentials, commit/push/deployment не затрагивались.

## People Local Staging Acceptance — 15.09.2026

**PASS** на `main`/HEAD `f13bfce` с незакоммиченными People-изменениями в этом checkout. Утверждено и реализовано правило A/B: новый `pending/active/paused` B сохраняется, завершённый A не открывается, Audit/Outbox фиксируют `reopen_blocked`, Notification Core уведомляет ответственного; уполномоченный сотрудник явно отменяет B и повторяет событие для A. Повторы и конкуренция проверены. Полная таблица «требование → проверка → результат → blocker» — в [PEOPLE_STAGING_ACCEPTANCE.md](PEOPLE_STAGING_ACCEPTANCE.md).

Финальный PostgreSQL 17.11 backend **414/414**, targeted conflict **17/17**, role **163/163**, API **73/73**, browser **5/5**, frontend build, check/drift, новый business upgrade (24 объекта), synthetic restore (179 таблиц/14333 строки/66 media), Notification worker пять причин и sensitive scan — PASS. Forgotten-password остаётся отдельным product gap вне приёмки. Следующая работа — Projects в изолированной ветке на базе этого checkout, с сохранением всех People-изменений. Production, реальные аккаунты/credentials, commit/push/deployment не затрагивались.

## Актуальный People Staging Acceptance — 08.09.2026

PostgreSQL 17.11: 410/410 PASS (handoff v13, skipped 0), API gate25 73/73, полная
синтетическая роль 95 permissions — 163/163, browser gate24 — 5/5, frontend build PASS.
Матрица 95 разрешённых / 26 запрещённых / 30 условных = 151; реальные права не выдавались.
После work_tasks0004: upgrade 24 связанных объекта PASS; restore 179 таблиц/11730 строк/
55 media PASS, ORM/SQL acceptance guard сохранён после restore.
Исправлены mixed view/write и NULL scopes, Admin/legacy lifecycle write paths;
проверены reviewer vs responsible, overdue concurrency и четыре People Email/In-App причины.
Текущий sign-off BLOCKED бизнес-конфликтом возврата старого onboarding при активном новом.
Единая таблица: docs/PEOPLE_STAGING_ACCEPTANCE.md; 95 consumer rows:
docs/OPERATIONS_DIRECTOR_CONSUMER_AUDIT.md. Forgotten-password — отдельный product gap.
Production/аккаунт Юлии/commit/push/deployment не затрагивались.

Дополнительно проверен отказ фактических pre-revocation tokens после restore-c.
Исправлены preflight/exit codes API harness и ожидания worker/Retry-After в browser harness.

## Исторические срезы (не текущий статус)

> Последнее исправление 08.09.2026: task.edit больше не меняет политику приёмки после
> первой публикации. Domain + DB trigger, ORM/bulk/Admin, sticky marker work_tasks0004;
> staging migration PASS, 7 focused tests PASS, live HTTP PASS, full backend 397/397 PASS.
> Прежний тест успешного обхода заменён проверкой запрета. Матрица 95/26/30=151.
> Полный consumer audit, целевая staging-роль и People Acceptance ещё INCOMPLETE.
> Production/аккаунт Юлии/commit/push/deployment не затрагивались.

> Последний срез 08.09.2026: **People Acceptance INCOMPLETE**, access gate BLOCKED.
> Backend 391/391 выполнены, skipped 0 (один тест воспроизводит существующий обход
> обязательной приёмки через task.edit — это не security PASS). API gate13 73/73;
> browser gate12 4/4 уже без Google Fonts interception. Business upgrade 21 связанных
> объектов PASS; restore 179 таблиц/5792 строк/23 media PASS. Матрица: 95 Да/26 Нет/30
> Условно, 151 код. Полная целевая роль не назначалась; task.edit удержан как BLOCKED.
> Реализован локальный Work-event reopen и expiry/overdue notification consumer.
> Production/реальные права/credentials/commit/push/deployment не затронуты.
> Канонический текущий отчёт: docs/PEOPLE_STAGING_ACCEPTANCE.md. Далее исторические срезы.

> Актуальный локальный срез 08.09.2026: PostgreSQL 17.11 **375/375 PASS**, skipped 0,
> Email включён; staging HTTP **73/73**, browser **4/4** (Google Fonts CSS изолирован).
> Два Notification Core падения устранены явным контрактом каналов + новыми тестами.
> HR-review старых/новых значений требует дополнительного scoped sensitive permission.
> Полный People Acceptance **INCOMPLETE/BLOCKED**, матрица доступа ещё DRAFT.
> Ниже исторические срезы; актуальные ограничения и evidence — в
> `docs/PEOPLE_STAGING_ACCEPTANCE.md`, раздел Authoritative checkpoint.
> Production не подключался; commit/push/deployment не выполнялись.

> Последняя перепроверка JWT staging, 08.09.2026: **362/362 PASS**, skipped 0,
> PostgreSQL 17.11, baseline Email off только в test-контейнере. При staging Email on
> два Notification Core теста падают из-за ожидания одной попытки вместо двух каналов;
> это ограничение общего acceptance пока не устранено. Live HTTP suspend → restore:
> старые access/refresh отклонены, новый login/refresh работает. Production в этом
> задании не подключался и не обновлялся; аккаунт Юлии оставлен заблокированным.
> Согласован будущий scope: все подразделения и бизнес-права, без управления
> аккаунтами/ролями/оргструктурой; точный allowlist ещё требует проверки косвенных прав.
> Полный People Staging Acceptance остаётся INCOMPLETE. Ниже — предыдущие срезы.

> 08.09.2026: People LOCAL STAGING ACCEPTANCE поверх `f13bfce` ещё не завершена.
> После согласованного исправления отзыва JWT/Django-сессий: **358/358 PASS**, skipped 0.
> Локально исправлены nullable FOR UPDATE при suspend/restore, повторный expiry-event
> и прямое завершение TASK-шагов без завершённой Task. Изменения не закоммичены.
> Append-only `accounts.0003_user_auth_version`, отдельный synthetic auth-upgrade и
> HTTP smoke PASS. Полные browser A–I/worker/общие upgrade gates ещё не выполнены.
> Production не затронут. Подробности: `docs/PEOPLE_STAGING_ACCEPTANCE.md`.

> 03.09.2026: Phase 2.3 зафиксирована checkpoint `067c60d`; Phase 2.4 Onboarding & Account Lifecycle реализуется локально поверх чистой границы.

**Обновлено:** 03.09.2026

**Ветка:** `main`
**Remote:** `origin` → `https://github.com/JohnyRiddle/ays_connect.git`

## Текущая задача

Phase 2.4 Onboarding & Account Lifecycle — COMPLETE локально; PostgreSQL 17.11 quality gate PASS, готово к отдельному checkpoint.

## Сделано

- production-фазы People Core 1.1A, Tasks 1.1B–1.1D и Service Catalog 1.2A;
- permissions, Audit и transactional Outbox;
- динамические поля, access rules и immutable schema snapshots;
- production `ServiceRequest` с UUID, immutable `REQ-*` нумерацией, snapshot значений и optimistic locking;
- строгий lifecycle NEW → ASSIGNED → IN_PROGRESS → WAITING/RESOLVED → CLOSED, отдельные reopen/cancel операции и histories;
- конфигурируемая маршрутизация через `AssignmentTarget`/`AssignmentResolver`, ручное назначение и история назначений;
- связь заявки с `work_tasks.Task`, manual/template creation и политики завершения execution-задач;
- SQL-level visibility policy, internal API `/api/internal/v1/requests/`, Audit и Outbox;
- PUBLIC/INTERNAL comments, revisions, mentions и soft delete;
- защищённые PUBLIC/INTERNAL attachments с общим storage security pipeline;
- watchers, расширенный PARTICIPATING, privacy-filtered Activity Feed и collaboration summary;
- отдельный SLA domain: версионируемые бизнес-календари, политики, warning thresholds и assignment rules;
- timezone-aware business-time calculator и preview API без изменения runtime заявок;
- SLAInstance, response metric, cycle-based resolution metrics, pause accounting, thresholds и breach history;
- транзакционные hooks ServiceRequest lifecycle, reconciliation и `process_sla` worker;
- SLA status/history API и request list filters;
- immutable escalation policies/bindings, cycle-aware executions и delayed schedules;
- notification intents, watcher/priority/reassignment actions и `process_escalations`;
- проект опубликован в `origin/main` коммитом `bfe8313` до текущего обновления документации;
- добавлены проектные документы передачи контекста и универсальные инструкции Codex.
- добавлен `backend/performance`: registry 30 метрик, исторические факты, версионируемые агрегаты, scoring policies и очередь пересчёта;
- добавлены full/incremental management commands, PostgreSQL `SKIP LOCKED` worker, internal API и SQL-level employee visibility;
- раздел SPA «Эффективность» переведён с legacy analytics на production Performance API;
- добавлен performance worker в pilot/server compose.
- production Work SPA: списки, фильтры, создание, detail и lifecycle actions для Tasks и Service Requests;
- динамическая форма заявки по published schema, PUBLIC/INTERNAL collaboration, SLA/history, watchers и защищённые attachments;
- создание execution Task из заявки, optimistic-lock conflict UX и единая нормализация API-ошибок;
- добавлен read-only lookup AssignmentTarget и человекочитаемые display-поля без изменения доменной логики;
- local pilot обновлён на существующей PostgreSQL БД; direct-route SPA fallback и Playwright smoke 7/7 проходят.
- controlled `RELEASE-GATE-1.6A` scenario восстановлен в отдельных PostgreSQL container/media volume: Employee, Task, Request, execution Task, SLA, Notification и Performance PASS;
- source/restored physical и DB SHA-256 обоих attachment совпадают; protected downloads после restore дают 401 без JWT и 200 с JWT;
- исправлен production Performance enqueue entity-type mismatch и добавлен regression test; baseline 254/254.
- Phase 2.1 расширяет существующий Employee без Person-дубликата: immutable `EMP-*`, historical assignments, manager hierarchy, termination/reactivation, Audit/Outbox;
- append-only migration `employees.0007` сохраняет legacy-поля и создаёт initial history rows для существующих сотрудников;
- два PostgreSQL upgrade rehearsal 0006 → 0007 и полный backend regression 276/276 проходят.
- Work/People frontend возвращён к единой компактной стилистике; все пункты основного меню маршрутизируются, незавершённые разделы имеют штатную заглушку, формы создания Task/Request открываются в правом drawer;
- production frontend build, Compose validation, deployment regression и local-pilot SPA/E2E gate проходят.
- Phase 2.2 расширяет единственную формальную модель `OrgUnit` и добавляет отдельный домен `Team`/`TeamMembership`, не заменяя legacy `FunctionalGroup`;
- добавлены `AssignmentTarget.TEAM`, детерминированные Team Resolver strategies, preview API, scoped permissions, Audit/Outbox и интеграция с увольнением сотрудника;
- PostgreSQL `btree_gist` exclusion constraint защищает всю историю членства от пересекающихся периодов, включая прямые записи вне service layer;
- PostgreSQL 17.11 Phase 2.2 gate: clean migration PASS, upgrade `employees.0007` → current PASS, `23/23` phase tests и `299/299` полный backend regression PASS.
- Phase 2.3 переиспользует `Employee.avatar`, добавляет OneToOne `EmployeeProfile`, типизированную field visibility и отдельный allowlisted `EmployeeDataChangeRequest` с optimistic locking, stale snapshot и запретом self-approval;
- добавлены self-service, directory и review endpoints в существующем `/api/internal/v1/people/`, защищённая выдача avatar, Audit/Outbox и уведомления через действующий Notification Core;
- frontend получил компактную страницу «Мой профиль», completeness, редактирование разрешённых полей и avatar actions; production build PASS.
- PostgreSQL 17.11 Phase 2.3 gate: clean migrations PASS, upgrade `employees.0010 → 0012` PASS, 27/27 phase tests (10 concurrency/security), полный backend regression 326/326 PASS без skipped.
- Phase 2.4 расширяет существующие Employee/User/Invitation/Profile, добавляет безопасную реактивацию, first-login, versioned onboarding templates/snapshots, dependency/responsible resolution, production Task integration и `SKIP LOCKED` reconciliation worker;
- append-only migrations `employees.0013–0015`; clean PostgreSQL 17.11 и upgrade `0012 → current` PASS; 16 Phase 2.4 tests, 10 PostgreSQL concurrency tests и полный regression 342/342 PASS без skipped;
- обнаружены и исправлены PostgreSQL nullable-join `FOR UPDATE` и termination/step deadlock с regression coverage; frontend production build PASS.

## Осталось

- перенести pilot-контур на сервер после получения hostname/network/secrets;
- выполнить расширенные RBAC, полный lifecycle Task/Request/SLA/Escalation/IN_APP/Telegram E2E с ограниченной группой пользователей;
- перед развёртыванием поверх старой базы подготовить план миграции существующих bigint ID к актуальным UUID-моделям либо использовать чистую базу.

## Известные проблемы и риски

- локальный Caddy CA не доверен встроенным браузером; trusted public HTTPS проверяется только на production hostname;

- локальный Docker PostgreSQL volume создан ранним прототипом и не должен обновляться без резервной копии/плана данных;
- production и legacy Tasks временно сосуществуют;
- production Performance API не заменяет legacy `/api/v1/analytics/`; новый SPA использует только `/api/internal/v1/performance/`, а legacy оставлен для совместимости;
- PostgreSQL 17.11 quality gate Phase 1.1D пройден: clean/upgrade migrations, Tasks 45/45, full backend 181/181 и 4 PostgreSQL concurrency tests;
- исправлена PostgreSQL-specific гонка при одновременном добавлении одного Task watcher;
- PostgreSQL 17.11 quality gate Phase 1.2C пройден: clean migrations, upgrade-клон Phase 1.2B → `0004`, 121 тест и 7 PostgreSQL concurrency/atomicity проверок;
- PostgreSQL 17.11 quality gate Phase 1.3A пройден: clean/upgrade migrations и 129 backend-тестов, включая 8 SLA domain tests;
- PostgreSQL 17.11 quality gate Phase 1.3B пройден: clean/upgrade migrations и 139 backend-тестов, включая 18 SLA tests и concurrency gate;
- PostgreSQL 17.11 quality gate Phase 1.3C пройден: clean/upgrade migrations и 154 backend-теста, включая 33 SLA/escalation tests, concurrency и E2E actions;
- устранена PostgreSQL-specific несовместимость `SELECT FOR UPDATE` с nullable outer join при публикации SLA policy;
- Docker Desktop и Linux engine доступны; gate выполнен в изолированном PostgreSQL 17 container.

## Рекомендуемый следующий шаг

Получить параметры production server и выполнить server-dependent gates. Не объявлять Work Core v1.0 до trusted HTTPS, reboot, Telegram и real-user UAT.

## Команды проверки

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test

cd ../frontend
npm run build

cd ..
docker compose run --rm backend python manage.py test
```

### Уточнение UI патча задач — 13.10.2026
В ветке патча удалены оставшиеся вкладка заявок и кнопка создания в карточке объекта; неизвестные и старые параметры tab возвращают вкладку зон. Это исправление ещё не опубликовано; текущий production frontend остаётся до PR #3.

## Production PR #3 — 13.10.2026

Опубликован RC `d6b2a8126018856377064d6865b784837f05fb6a`: патч задач интегрирован с опубликованным дизайном, историей обновлений и компактным списком объектов. Убраны меню/вкладка/создание сервисных заявок; исторические данные сохранены. Fresh-copy PostgreSQL 672/672 и integrated browser 11/11 PASS; live HTTPS 12/12, authenticated read-only UI, 7/7 runtime healthy PASS. Сохранены импорт справочника, users/People/grants и 62 pending location.*. Frozen DB/media/frontend restore 202 таблиц PASS, успешное окно 77.532 с. Прежнее автоматическое возвращение к old runtime заняло 81.672 с, после чего точка обновлена; migration downgrade не выполнялся.

Руководители подразделений ещё не назначены: новые задачи требуют настройки People; 4 старые задачи требуют department перед передачей в работу. Corporate Telegram API установлен, постоянный adapter и внешняя доставка выключены. Полный отчёт, immutable images, восстановление и границы: [TASK_PATCH_DEPLOYMENT.md](TASK_PATCH_DEPLOYMENT.md). После новых writes frozen point нельзя восстанавливать вслепую.

## Сотрудники и очистка задач — 14.10.2026

По явному запросу владельца в production созданы пять карточек/обычных учётных записей: четыре руководителя подразделений и управляющая «Профилака». Четыре руководителя видят 51 действующий объект, управляющая — только «Профилак». Название «Техническая служба», её пустое юрлицо и отсутствие руководителя УК сохранены. Адреса-заглушки, логины и пароли выданы в защищённом локальном файле; настоящие ящики не создавались.

Четыре прежние Work Task удалены, Work/legacy Tasks=0. Проект сохранён, история связей архивирована в Audit; старые idempotency-запросы не воссоздают задачи. Backups/restore 202 таблиц, полный rollback и неизменяющий replay, проверка пяти логинов, назначений/доступов и реальный HTTPS login PASS. Backend и сайт не останавливались, шесть workers возобновлены после 66.797 с; images/код не менялись. Это устраняет прежний blocker четырёх задач без department; новые задачи могут назначаться четырём настроенным руководителям. УК по согласованию остаётся без руководителя. Telegram adapter по-прежнему отдельно не подключён.

Подробности, границы и восстановление: [STAFF_SETUP_TASK_RESET_2026_10_14.md](STAFF_SETUP_TASK_RESET_2026_10_14.md). Текущие изменения — только документация, без нового commit/push.

## Telegram из профиля — 14.10.2026

Уточнение аналитики 14.10: локально убраны оставшиеся карточки «Решено заявок», «SLA решения» и «Backlog заявок» из production performance UI; четыре показателя задач расположены в две колонки, блок переносов сроков занимает полную ширину. Из пояснения убрано упоминание заявителя. API/исторические расчёты не изменялись. Изменение ещё не опубликовано; Telegram остаётся выключен до предоставления доступа. Проверки этого изменения приведены в конце [отчёта PR #3](TASK_PATCH_DEPLOYMENT.md).

Штатная доставка через `@AYS_ai_expert_bot` подготовлена, но НЕ включена: production-сервер не соединяется с `api.telegram.org:443` на трёх адресах, другие сайты доступны; Telegram также не достигает публичного webhook. Канал снова выключен, подготовленный receiver остановлен, новые Start сохранены у Telegram. Пользовательский путь: привязка из собственного профиля → Start → уведомления ответственному в его личный Telegram. Transport `direct`, доставка у существующего notification_worker; отдельного pull-sender нет. Images и миграции не менялись. Fresh-copy 202 таблицы, 69 тестов и профиль/webhook/ответственный/unlink probe PASS; две проверки восстановления receiver PASS на Windows/Linux. 7 основных runtime healthy, задач 0; реальная production-привязка и сообщение не подтверждены. Нужен исходящий доступ сервера к Telegram или HTTPS-прокси. Вчерашние реальные сообщения шли с клиентского компьютера через copy harness. Secrets вне Git, конфигурация и evidence сохранены. [Отчёт и продолжение](TELEGRAM_PROFILE_PRODUCTION_2026_10_14.md).

## Конструктор чек-листов — локальная реализация 14.10.2026

По выбору владельца реализованы шаблоны и чек-листы в задачах без расписаний.
Расширены существующие production UUID-сущности work_tasks, legacy данные
сохранены. Конструктор доступен через `/checklists` и прежнюю hash-ссылку:
разделы, порядок, обязательность, шесть типов ответов, предпросмотр/копирование/
архивирование. В задаче — прикрепление версии, ответы и комментарии, прогресс,
блокировка завершения при незаполненных обязательных пунктах. Аддитивная миграция
0009, Permission/Audit/Outbox и version conflict сохранены. Production и Telegram
не менялись. [Контракт, ограничения и проверки](CHECKLIST_BUILDER.md).

Финальный gate: PostgreSQL Tasks + Notifications **142/142 PASS** (включая
13 новых, реальную конкуренцию и upgrade старого completed checkbox),
Playwright **4/4 PASS** на desktop/mobile, TypeScript/Vite, Django check,
makemigrations --check и diff check PASS. Ранние полные прогоны выявили stale
Task при удалении и перекрытие from-template DELETE-маршрутом; исправлены и
перепроверены профильным прогоном. Полный 685 на финальном коде повторно не
запускался. Готово локально, без deployment/commit/push.

## Production: конструктор чек-листов — 14.10.2026

Опубликован RC `7d82e296320c`: конструктор шаблонов и типизированные чек-листы
в задачах, обязательность, версии/права/история; убраны показатели заявок.
Fresh-copy PostgreSQL **685/685 PASS**, init сохранил 202 таблицы,
реальные роли/шесть типов **9/9 PASS** с rollback fixtures. Protected frozen
DB/media/frontend restore PASS; окно **81.016 с**,
production **7/7 healthy**, 14 HTTPS 200, actual read-only UI **3/3 PASS**,
0 HTTP writes. Telegram остался выключен, receiver остановлен.
Актуальный Compose — `/opt/ays-connect/compose-current.sh`; прежний Telegram
entry point сохранён с новым набором images. Полный финальный gate заменяет
прежнее ограничение локального прогона. [Выпуск и recovery](CHECKLIST_BUILDER_DEPLOYMENT_2026_10_14.md).

## 14.10.2026 — компактный чек-лист в карточке задачи (локально)

После замечания владельца обновлена компоновка прохождения: номера пунктов,
индикатор общего прогресса, раскрываемое прикрепление шаблона и комментарии.
Сохранённые ответы показаны текстом вместо неактивных полей, сохранены
время ответа и штатный сброс для изменения. API, права и данные не менялись.
Проверки: TypeScript, Vite и browser 6/6 (1280/390 px, все шесть типов,
комментарии, сохранение числового нуля, progress, отсутствие overflow).
Ветка codex/checklist-task-layout; публикация в production не выполнялась.

## 14.10.2026 — параметры задачи и поиск наблюдателей (локально)

По замечанию владельца sidebar разгружен: подразделение оформлено полем,
редактирование параметров перенесено под значения, повтор приоритета убран
(приоритет остаётся в шапке). Наблюдатели добавляются по одному из выпадающего
поиска по имени/фамилии без постоянно открытого списка и длинных пояснений.
Поиск использует прежний participant-options API и его ограничения видимости;
уже добавленные сотрудники исключены. Поддержаны debounce, Escape, стрелки,
Enter, закрытие по потере фокуса, загрузка/ошибка/пустой результат.
Удаление — отдельное красное текстовое действие и inline подтверждение.
Новые browser проверки на 1280/390 px: поиск, последовательное добавление,
исключение дублей, клавиатура, пустой ответ, отмена/подтверждение удаления.
Общий browser gate 8/8 PASS; TypeScript PASS. Данные production не менялись,
commit/push/deployment не выполнялись; прежние Telegram файлы сохранены.


## 14.10.2026 — интерфейс чек-листов и наблюдателей опубликован

PR #5 merged; frontend RC `cf5a47a31c21cdcb87a45e32a78e346e8925bb3a`. Browser 8/8, TypeScript,
immutable build, HTTPS 10/10 и actual read-only owner UI desktop/mobile PASS.
7 core services healthy без перезапуска. EFS frontend recovery сохранён,
DB/API/migrations не менялись. Telegram выключен.
[Evidence и возврат](TASK_LAYOUT_DEPLOYMENT_2026_10_14.md).


## 15.10.2026 — IT/закупки созданы, исправления задач локально

Production: IT — Веселков Сергей, Отдел закупок — Могунов Эдуард; новые
карточки/placeholder accounts и доступ каждому к 51 объекту. Rehearsal rollback,
защищённый pg_dump, сохранность прежних User/People/OrgUnit/Position, replay
и owner assignment-options PASS. Данные задач не менялись.
Локально: preview срока для всех приоритетов, скрытая пустая панель чек-листов,
пометка существующих наблюдателей, просмотр изображений и @ в чате.
PostgreSQL 21/21, browser 12/12, TypeScript/Vite/check/drift/diff PASS.
Согласования ожидают уточнения маршрута. Код не публиковался.
[Подробности и защищённые доступы](TASK_USABILITY_2026_10_15.md).

## 15.10.2026 — WORK-TASKS-APPROVALS-01: локальная реализация / staging

Независимые согласования после явного действия на @упоминании: PENDING,
CLARIFICATION_REQUESTED, APPROVED, CANCELLED; обязательный текст решений,
повторные раунды, PostgreSQL immutable history/identity/consistency guards,
RBAC + Task/Object/internal scope, atomic Audit/Outbox, idempotency/version API.
TaskService/Task.save не вызываются, поля/истории Task и SLA не меняются.
Telegram Notification Engine интегрирован; внешние отправки staging отключены.
Новые permissions автоматически существующим ролям не выдаются.

Full PostgreSQL **708/708 PASS**, focused **104/104**, browser real API **2/2**
на 1280/390 px, прежний UI gate **12/12**, TypeScript/Vite/check/drift PASS.
Standalone approval OpenAPI: 7 paths / 8 operations / 12 schemas, validation PASS;
прежние diagnostics общей схемы сохранены в отчёте. Local staging loopback3035/8035,
отдельная synthetic PostgreSQL DB. Production этого патча не касались.
Ветка codex/work-tasks-approvals-01, без commit/push/deployment; прежние dirty
usability-изменения и отложенные Telegram-файлы сохранены.
[Аудит, контракт, staging/demo и проверки](WORK_TASKS_APPROVALS_01.md).

## 15.10.2026 — согласования опубликованы, production принят

По явному разрешению выполнены commit/push, merged PR #6/#7 и production
deployment. Runtime `c5264e668f5b4bf1fb4e8b848de558546bd17019`.
Независимые согласования в комментариях и предыдущие usability-исправления
доступны; поиск сотрудников больше не фильтрует родительскую задачу по фамилии.
Согласованные четыре approval permissions выданы семи сотрудникам только
со scope `participating`, без расширения доступа к задачам/объектам.

Финальная свежая копия: 204 таблицы, PostgreSQL **709/709 PASS** с production
hasher, API **14/14 rollback**, staging browser **2/2**, прежний UI **12/12**.
Frozen DB/media/frontend восстановлены и сверены до открытия записи;
финальное переключение **92.375 с**, 204 таблицы сохранены. Public HTTPS
**16 PASS**, core **7/7 healthy**, read-only browser **5 PASS**, 0 HTTP writes.
После workers сохранены 11 identity/org/RBAC таблиц. Временные production-копии
остановлены; локальный synthetic staging оставлен. Telegram/receiver выключены.
[Полный отчёт, два выпуска, защищённые точки и проверки](WORK_TASKS_APPROVALS_RELEASE_2026_10_15.md).

## 15.10.2026 — дополнительные участники согласований

По явному запросу Ливеринову Ивану и Могуновой Юлии назначена отдельная роль
`approval_participants_20261015`: четыре `task.approval.*` и базовые
`task.view`/`task.comment`, только scope `participating`. Ровно два назначения,
без глобального доступа к задачам/объектам. У Ивана ранее уже был superuser.
У Юлии вход был отключён; включён после отдельного явного подтверждения,
пароль и прочие права не менялись. Audit/Outbox записаны штатными сервисами.
API approval-options проверен в обоих направлениях на временной общей задаче
в rollback-транзакции; тестовые данные не сохранены. Самосогласование исключено:
на исходном скриншоте Иван упоминал самого себя, что объясняло пустой список.
Доказательства в защищённом release evidence: `approval-rights-*` и
`yulia-account-enabled.json`. Код и runtime не менялись; Telegram выключен.

Уточнение после проверки реальной задачи: Юлию скрывал object scope OhMyGesh.
По отдельному подтверждению пользователя ей назначена существующая роль
`employee_objects_viewer` на **51 действующий неархивный объект**, через
RoleService с Audit/Outbox. Роль даёт `location.view` в контексте объекта
и `people.profile.view_self`; global/location management права не выдавались.
API поиска «Могунова» на всех трёх текущих задачах возвращает Юлию.
На TASK-000007 проверены временный watcher и approval-options; изменения
проверки полностью rollback, все поля задачи неизменны. Постоянно наблюдателем
она не добавлялась: это действие остаётся пользователю. Evidence:
`yulia-object-access-proof.json` в защищённом release evidence.

## 15.10.2026 — прямой выбор согласующего (локально/staging)

По новому запросу подготовлен выбор сотрудника непосредственно в форме
согласования под своим опубликованным комментарием — без предварительного @
и без добавления в наблюдатели. Кандидаты требуют активного аккаунта,
видимости в справочнике инициатора, доступа к объекту и существующих прав
просмотра/согласования. Просмотр кандидатов доступа к задаче не даёт.
TaskApproval после отправки становится основанием участия для просмотра,
чата и approval permissions; TaskWatcher/roles/grants не создаются.
Права изменения статуса/сроков/исполнителя/чек-листа не расширяются.
Internal scope проверяется отдельно; отзыв прав/доступа к объекту закрывает
доступ. История сохраняется, все поля Task/SLA неизменны.

Полный PostgreSQL **711/711 PASS**; browser с реальным API **2/2 PASS**
на 1280/390 px без предварительных mentions/watchers/назначения исполнителем;
TypeScript/Vite, Django check, migration drift и diff check PASS.
OpenAPI 7 paths / 8 operations / 12 schemas, validation PASS. Миграций нет.
Synthetic fixture: `.codex/tmp/approval-staging/direct-fixture.json`, интерфейс
loopback 3035/8035; внешние каналы выключены. Код не закоммичен и не опубликован,
production не менялся. Предыдущие незакоммиченные записи прав и Telegram-файлы
сохранены. Контракт обновлён в WORK_TASKS_APPROVALS_01.md.

## 15.10.2026 — упрощение чек-листов (локально/staging)

Название и описание по «?» в круге; описание открывается небольшим popup,
в конструкторе там же редактируется. Новые пункты — название и галочка,
без схемы ответа/раздела/подсказки/обязательности/границ. В задаче галочка
сохраняется сразу и снимается тем же контролом с version, без отдельной кнопки.
Скрыты технические подписи/комментарии/даты/счётчики; прежние typed answers
и скрытые схемы сохранены без конвертации и потери данных.

Аддитивная `work_tasks.0012_checklist_description` добавляет snapshot описания
экземпляру задачи; backfill только для точно совпадающей версии шаблона.
PostgreSQL **26/26 PASS**, browser **12/12 PASS**, дополнительно uncheck **1/1**
и финальный mobile **2/2**; TypeScript/Vite/check/drift/diff PASS.
Миграция/новая bundle применены только к synthetic staging loopback3035/8035.
Production, commit/push не выполнялись. Предыдущие незакоммиченные согласования,
записи выдачи прав и Telegram-файлы сохранены. Подробнее: CHECKLIST_BUILDER.md.

## 15.10.2026 — PR #8: упрощённые чек-листы и прямой выбор опубликованы

По явному запросу выполнены commit/push/merge и production deployment.
Feature/runtime `e24a9281cdf27bb0ece66a23a5d27fd8edd70ec6`, merge `0acb0e0`.
Название чек-листа, описание по «?», новые пункты с названием и мгновенной
галочкой. Старые typed answers сохранены. Согласующий выбирается прямо
в форме без предварительного @/наблюдателя; TaskApproval даёт участие только
в конкретной задаче с существующими permissions и object/internal scope.
Task.status/SLA/сроки/приоритет/назначения не меняются. Новых grants нет.

Свежая защищённая production-копия: **204 таблицы**, **712/712 PostgreSQL PASS**
с production password hasher, API **14/14 rollback** на настоящих ролях и объекте.
Browser **12/12 UI + 2/2 real API staging**, TypeScript/Vite/check/drift/OpenAPI PASS.
Применена только аддитивная `0012_checklist_description`; snapshot описания
независим от последующей версии шаблона. Frozen DB/media/frontend восстановлены
и сверены до открытия записи. Frozen UTC `2026-10-15T16:11:55.973140+00:00`,
окно **96.125 с**; сохранены исходные 204 таблицы, повторный migration plan пуст.
Production API **14/14 rollback**, HTTPS **16 PASS**, core **7/7 healthy**,
production browser **6/6 PASS**, 0 HTTP write attempts. Telegram/receiver выключены.
Operational wrappers согласованы с runtime; 11 identity/org/RBAC таблиц
сохранены после запуска workers, временная production-копия остановлена.
[Отчёт выпуска и защищённые доказательства](SIMPLE_CHECKLISTS_DIRECT_APPROVAL_RELEASE_2026_10_15.md).

## 16.10.2026 — отдельные страницы доступа сотрудника (локально)

«Объекты и права» и «Доступ и группы» вынесены из карточки на
`/people/employees/{id}/objects` и `/people/employees/{id}/access`.
В карточке — раскрывающееся меню «Настройки сотрудника». На страницах есть
возврат, имя сотрудника, взаимные ссылки, поиск, группировка одинаковых ролей
и адаптация к мобильному экрану. Объектные назначения не загружаются в карточке.
Редактор прежних назначений сохранён с поиском объектов и ограничением списка.
Backend/RBAC/permissions/payloads не менялись, миграций нет. Production не менялся;
commit/push не выполнялись, три прежних Telegram-файла сохранены.
Browser **4/4 PASS** на 1280/390 px, TypeScript/Vite/diff check PASS.
[Описание и проверки](EMPLOYEE_ACCESS_PAGES_2026_10_16.md).

16.10.2026: чек-листы задач дополнительно выделены карточками с контрастным
фоном, рамкой, оранжевым акцентом и иконкой заголовка. Логика не менялась.
Светлая/тёмная темы, 1280/390 px: browser **2/2 PASS**, TypeScript/Vite/diff PASS.
Доработка локальная, вместе с непубликованными страницами доступа сотрудников;
commit/push/deployment не выполнялись, прежние изменения сохранены.

## 16.10.2026 — PR #9: страницы доступа и карточки чек-листов опубликованы

По явному запросу commit/push/merge/publication завершены. Frontend
`0152e0677c0fc98e281663d6e330e07579d46db9`, merge `eaabe27`.
Отдельные страницы объектов/прав и доступа/групп с меню из карточки сотрудника,
поиском и группировкой ролей. Чек-листы выделены контрастными карточками.
Browser **4/4 employees + 12/12 checklists PASS**, TypeScript/Vite/diff PASS.
Production HTTPS **16 PASS**, browser **7/7 PASS**, 0 HTTP write attempts,
core **7/7 healthy**. Восстановление защищённой frontend-копии (32 файла)
проверено до публикации, 25 прежних assets сохранены. Без простоя.
Backend image/RC `e24a928`, БД, миграции, права и API не менялись; server/workers
не перезапускались. Operational wrappers/frontend metadata обновлены,
Telegram/receiver выключены; три отложенных Telegram source-файла сохранены.
[Полный отчёт](EMPLOYEE_UI_RELEASE_2026_10_16.md).

## 16.10.2026 — отдельные блоки вложений/чата и mention popup (локально)

Задача использует отдельные карточки с промежутками; вложения и чат выделены
рамкой/оранжевой верхней границей, чат имеет явный заголовок. Новые упоминания
показываются возле колокольчика справа сверху, без старого backlog/повторных
показов; опрос 10 секунд + focus, автоскрытие с паузой hover/focus.
Закрытие не отмечает read, «Открыть задачу» использует штатный read endpoint.
Notification API дополнен read-only is_mention с актуальным Task/Object/internal
scope; дедупликация существующего Notification Engine сохранена, миграций нет.
PostgreSQL **32/32 PASS**, browser **14/14 PASS**, повтор popup **2/2**;
TypeScript/Vite/check/drift/diff PASS. Production/commit/push не выполнялись,
Telegram выключен, отложенные файлы сохранены.
[Поведение, ограничения и проверки](TASK_DISCUSSION_MENTIONS_2026_10_16.md).

Дополнение 16.10.2026: сообщения задачи перенесены в ограниченную прокручиваемую
область, composer — под неё. Начальное открытие/своя отправка показывают последние
сообщения; чтение переписки выше не сбивается вводом и изменением размеров.
Согласования и @подсказки сохранены. Browser **16/16 PASS**, повтор scroll/resize
**2/2 PASS**, TypeScript/Vite/diff PASS. Все изменения этого обсуждения локальные,
без commit/push/production deployment; предыдущая подготовка сохранена.
