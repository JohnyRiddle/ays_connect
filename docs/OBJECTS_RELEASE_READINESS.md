## 09.10.2026 — Objects production release PASS; PR #1

Storage gate **PASS для действующего backup/restore контура**: 24 исходных файла скопированы на LUKS2 с полным совпадением path/size/SHA-256/UID/GID/mode/mtime; guard отказал на обычном ext4 (exit 78, ноль новых файлов), missing bind source — exit 125 без fallback. Новый periodic backup 12:33:16 UTC корректен, история сохранена; retention отключён. Исходные 24 файла остаются отдельно на незашифрованном `ays-connect-production_backup_data`: **не вся история зашифрована**, удаление не выполнялось. Persistent crypttab/fstab manual unlock/noauto и Compose bind create_host_path=false проверены; reboot не выполнялся. Отдельная DPAPI key copy восстановлена и проверена. Guard и обязательный override опубликованы в deployment; source/backend/frontend runtime и схема относительно RC220ffac не изменены.

Новая frozen rollback точка **09.10.2026 12:51:50.390359 UTC**: исходная production версия main64f85fa, 101 migrations; Location/Facility/Zone/Company/Region/Cluster/LegalEntity/OrgUnit отдельно 0, Users 5/Employees 4 с явно разрешённой test persona, RolePermission 125/EmployeeRole 1. **O0 PASS / mapping-transfer N/A только этого snapshot**, ограничения encoded/name-only скана сохранены. EFS off-host DB/media SHA и restore именно из этих файлов PASS; дополнительная age copy расшифрована отдельно защищённым ключом и дала те же SHA. Полный init копии и production — PASS: ровно access_control 0003 + organizations 0004–0007, migrate/seed_permissions/collectstatic/chown, 101→106, повторный plan [], check/drift PASS, реальные grants сохранены. Copy 196/1981→198/2004, 192 старых tables unchanged, четыре ожидаемых catalog/migration delta, catalog label renames 0. Дополнительный online rehearsal API **32/32, 17.762s**; полный 585 и browser 6 не повторены, runtime не менялся.

Live SSH-only smoke **PASS в согласованном контексте**: owner normal UI create, намеренно прерванный первый ответ только smoke relay, идентичный UI replay с тем же Idempotency-Key/payload — upstream 201→200, тот же UUID, один idempotency record. Non-staff/non-superuser persona: denied detail 404/create 403/list count 0/lookups без скрытых IDs; location-scoped view/manage_zones — list count 1/detail 200/zone create 201/zone count 1/stale repeat 409, root create вне контекста/edit 403. Related counts People/Work/Requests/Projects/participation 0, реальные People/Tasks/Project detail 404; Requests collection 200 с count 0, это scoped empty result, не 403. Legacy write persona 403, smoke admin ingress 403; live owner legacy 405/Admin write-form **не проверялись**, прежние code/copy проверки сохраняются. Positive root create через LegalEntity **NOT PERFORMED/N/A без разрешённого контекста**; scoped positive create здесь — зона в явно разрешённом test parent, никаких искусственных LE/OrgUnit.

Test scope отозван; persona User 6 / Employee fa09c72e-5a01-49f4-a7da-8e32856ea903 штатно inactive/terminated, test role inactive, assignments 0, session revocation audited. Fresh valid access до cleanup 200, тот же access после 401, refresh 401/new login 401; исходные live tokens также проверены по public HTTPS — 401/401/401. История не удалена. Root `4c2f1c70-3ab6-42bc-90e0-5e056109c257` и zone `a8e67240-e071-4a14-bd91-1c860912263e` закрыты/архивированы через ObjectService с policy checks оператором по SSH; **не заявляется UI/API cleanup**. Ровно 2 Location, 1 idempotency, 5 Audit и 5 Outbox; новая зона под архивным parent отвергнута domain ValidationError без новых rows/events. Ни ответственных, ни бизнес-связей, ни operating status не создавали.

Production открыт **13:06:33.407 UTC (20:06:33.407 Asia/Novosibirsk)**. Maintenance window 12:51:11.520→13:06:33.407 UTC — **921.887s / 15m21.887s**; точный момент остановки proxy отдельно не записан, это измеренное окно maintenance, а не отдельный таймер proxy. Backend/6 workers healthy, HTTPS/live/ready двух доменов **6/6 HTTP 200**, frontend volume 8/8 files exact immutable artifact. Workers запущены 13:05:16.819 UTC: с этого момента возможны реальные новые writes; **blind restore rollback point запрещён**. Outbox failed=0, пять location.* pending/attempts=0/unique event IDs: consumers для них не зарегистрированы, **доставка не проверена и не объявляется PASS**; NotificationDeliveryAttempt=0/test employee deliveries=0. Backup running encrypted/retention disabled, owned smoke/copy helpers/tunnel stopped, encrypted volumes/evidence сохранены. Исходные 13 dirty-файлов и CRLF-only views.py побайтово сохранены.

**Code/synthetic acceptance PASS; snapshot O0/upgrade PASS; deployment PASS для согласованного pilot scope.** Release runtime RC `220ffac89568a0e7b2aa493a4b599e0aa1946772`; backend/6 workers 416/416 source files exact RC. Фактический merge SHA фиксируется в GitHub PR #1; merge выполняется после acceptance и не запускает повторный init/deployment. Recovery owner Иван, хранение 90 дней (fresh point минимум до **07.01.2027 12:51:50 UTC**), удаление только его решением. Unencrypted retained source, portable/off-device DPAPI recovery, full-disk BitLocker/free-space remanence, populated attachment compatibility, encoded/name-only references и неподтверждённые live сценарии остаются явными ограничениями. [Полные SHA, команды и startup/rollback](OBJECTS_RELEASE_READINESS.md).

### Фактические images и rollback evidence выпуска

| Назначение | Immutable image |
|---|---|
| Backend / шесть workers / выполненный init | `ays-objects-rc-065325677b2c@sha256:83c65c8816fcff3c09ea37482282edc13397fd67440dba8bb83d0eadfb98ffa6` |
| Выполненный frontend_assets / deployed bundle | `ays-objects-rc-065325677b2c@sha256:69fe92bab0926f813ea68d2bee60c3746883e876a4eb8ea6108a21251fe3b85f` |
| Proxy, прежний TLS config | `caddy@sha256:af32e97399febea808609119bb21544d0265c58a02836576e32a2d082c262c17` |
| PostgreSQL 17.11 / guarded periodic backup | `sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73` |

Fresh DB SHA `1752326f9eb1ef8f4ba7d8c8be61557e53d105604fa5339e735aa8e51d628f80`; media SHA `63e15ba15ac544c6de0d349438e999d5025d7b1ff3accf7bf1e89577f4225d63`; дополнительный off-host age SHA `5ec83e0d0da1e81551be9782919636d8a65095b052587e77853900e4ea8a5f34`. Это новые release evidence; прежний snapshot 09:49 и его SHA не перезаписаны. Raw DB/media на server LUKS и off-host EFS; identity recovery происходит только в памяти/age stdin, plaintext private key file не создаётся.

Manifest до/после: private `periodic-storage-manifests.json`; negative proofs `periodic-storage-negative.json` / `periodic-storage-missing-bind-proof.json`; positive/new-backup proof `periodic-storage-cutover-proof.json`. Полные raw rows/inspect/env/persona credentials остаются в encrypted private storage вне Git; в Git только результаты и параметры без секретов. Fresh point evidence — `I:\AYS Connect\Objects\release-220ffac\private\rollback-20261009T125106Z` (фактический directory ID смотреть в protected release-state). Snapshot export online rehearsal `00000019-0000DEEE-1`, получен 12:39:12.040 UTC; это время получения baseline, **не точное время открытия snapshot transaction**. Его SHA `fc034f79a77a026b57100edcfc6237277b5b8b427d496bece57ad54b9615b490`, не финальная rollback точка.

Фактические команды production: Compose project `ays-connect-production`, configured env `/opt/ays-connect/.env.production` (значения не выводились), файлы package `source/docker-compose.prod.yml`, `source/docker-compose.iiko.yml`, `production.override.yml`, `periodic-backup.override.yml`. `run --rm --no-deps init` выполнен **один раз**, затем `run --rm --no-deps frontend_assets`, `up -d --no-deps --no-build --force-recreate backend`, после smoke `up -d --no-deps --no-build --force-recreate` шести workers. Proxy возобновлён по прежнему сохранённому ID/TLS config; backup unpause по новому guarded ID без повторного запуска timer loop/retention. `check`, `migrate --check`, `makemigrations --check --dry-run`, empty MigrationExecutor plan — PASS. Image/runtime/bundle verification и data/grant comparisons относятся к этому окончательному коду.

### Постоянный guarded backup и startup после reboot

Versioned guard: `deployment/objects-periodic-backup-guard.sh`, SHA `e7134f0d61ba56f924d98e748ae7f7c4bd1058191ea5eb645d7c6cbcbafe9ddd`; versioned обязательный шаблон `deployment/objects-backup.override.yml`. Compose template с явными `OBJECTS_BACKUP_IMAGE`, `OBJECTS_BACKUP_DEVICE`, `OBJECTS_BACKUP_DIRECTORY`, `OBJECTS_BACKUP_GUARD_PATH` проверен `config --quiet` и сравнением image/entrypoint/command/ro-root/env/device/bind paths с **действующим** backup. Backend/frontend images не пересобирались; эти два infrastructure файла не меняют Django/React runtime/schema. Шаблон не содержит credentials и запрещает create_host_path. Guard сверяет `/proc/self/mountinfo`: major:minor ожидаемого crypt device + source `/dev/mapper/objects-220ffac-recovery` + ext4 + mount `/backups`; до успеха нет mkdir/pg_dump/tar/retention. Retention отсутствует в guard. Только shell-guard positive/negative и Compose checks необходимы для этих infrastructure изменений; backend regression повторно не требуется.

Persistent source `/home/ivan/ays-objects-rc-065325677b2c/encrypted-storage/storage.luks`, mapper `/dev/mapper/objects-220ffac-recovery`, mount `/home/ivan/ays-objects-rc-065325677b2c/encrypted-storage/mounted`; backup directory внутри него `backups/periodic-production`. `/etc/crypttab`: image / none / luks,noauto; `/etc/fstab`: mapper → mount / ext4 / noauto,nosuid,nodev. Прежние config files сохранены в encrypted recovery-proof. Server plaintext key file отсутствует. После reboot:

1. Recovery owner предоставляет восстановленный ключ из защищённой отдельной DPAPI copy только memory/stdin; открыть LUKS, mount по fstab. Не записывать ключ и не создавать fallback directory.
2. Проверить `cryptsetup status`, точный `findmnt SOURCE`, свободное место и guard SHA. Major:minor может измениться; обновлять EXPECTED_BACKUP_DEVICE **только после** proof того же encrypted mapper, не брать автоматически с обычного каталога.
3. Применять production Compose с pinned override **и** guarded-backup override. Missing bind source → Docker error; подставленный обычный каталог → guard exit 78. Обычный base compose без required override не является разрешённым production startup.
4. Запустить guarded backup без retention; проверить новую copy/hash/readability, сохранность истории. Restored DB/API containers restart=no; старые bind-retained volumes требуют восстановления mounts и proof перед запуском. Фактический reboot не проводился.

Исходный unencrypted backup named volume сохранён, obsolete stopped backup container удалён после сохранения exact inspect/config; новый backup тот же PostgreSQL image и configured DB/media, обязательный guard/retention disabled. Original 24 files нельзя объявлять encrypted или удалять по автоматически истёкшему сроку. Их возможная отдельная очистка и forensic free-space wipe требуют решения владельца; в этом выпуске не выполнены.

### Recovery после новых writes

Workers barrier 13:05:16 UTC, public writes открыты 13:06:33 UTC. При STOP после этих моментов: закрыть ingress/остановить writers, сохранить новую защищённую аварийную DB/media точку и определить/reconcile/replay новые данные/доставки с Иваном. **Запрещены blind restore старой точки, автоматические reverse migrations, DROP/перезапись действующей DB.** Сохранять изменённые volumes для расследования. Frozen rollback point содержит активную тогда test persona: при любом согласованном восстановлении штатно отозвать/terminate её и credentials до открытия пользователей, не восстановить временный доступ молча. Производственные реальные account/grant changes после snapshot сохранять согласно recovery-owner решению.

### Исторические записи до storage cutover и выпуска

## 09.10.2026 — release STOP до maintenance; temporary persona закрыта

Повторная фактическая storage проверка обнаружила незакрытый обязательный gate: действующий `ays-connect-production_backup_data`, 24 файла / 8124 KiB, находится на `/dev/sdb1 ext4`, без подтверждённого crypt-слоя. EFS off-host/LUKS rehearsal storage не защищает этот действующий volume. Перед GO требуется проверенное переключение всего periodic backup storage на encrypted mount с сохранением bytes/UID/GID/modes, возобновлением без запуска retention и отказом записи при отсутствии encrypted mount. Пользовательский downtime **0 секунд**; production init, merge, deployment и новый release backup не выполнялись. Прежняя версия production сохранена.

Temporary production persona User 6 / Employee fa09c72e-5a01-49f4-a7da-8e32856ea903 штатно закрыта после STOP: active assignments 0, User inactive, Employee terminated/inactive; audited session revocation, фактический access до закрытия 200, тот же access после 401, refresh 401, новый login 401. Реальные User values не менялись, audit/rows сохранены. Live denied/scoped Objects acceptance **NOT PERFORMED**, прежний rehearsal PASS относится только к копии; этот cleanup PASS не является разрешением пропуска live gate. Для следующей попытки проверить статус persona и свежий baseline заново; не использовать уже отозванные credentials.

Production после STOP: 11 running containers, backend и 6 workers healthy, backup running/unpaused, оба HTTPS домена и live/ready — 6/6 HTTP 200. Исходные dirty bytes сохранены. Snapshot O0/upgrade PASS и legacy N/A остаются ограничены snapshot 09:49 UTC; production readiness **CONDITIONAL**, deployment **NOT PERFORMED**. Разрешение release сохраняется после устранения STOP, повторное разрешение предусмотренных шагов не требуется.

# Objects — release readiness, 09.10.2026

## 09.10.2026 — обязательные pre-maintenance ресурсы подготовлены

Новое разрешение пользователя допускает одну маркированную temporary production persona/Employee без staff/superuser, временные минимальные назначения только в smoke-контексте, аудит изменений и обязательное штатное закрытие с проверкой старых credentials. Создана **одна** persona `RELEASE-SMOKE-220ffac-PERSONA-8368bd894544` (User 6 / Employee fa09c72e-5a01-49f4-a7da-8e32856ea903), **0 grants/assignments**, существующие User/roles/grants не менялись. Django UserManager + EmployeeService + Audit применены без invitation и notification delivery event types. Первая защитная транзакция откатилась до commit из-за ошибочного сравнения служебного ModelState; повторное сравнение persisted values исправлено, orphan rows отсутствуют. Пропуск integer sequence значения возможен после rollback, это не дополнительный аккаунт. Normal login/me через SSH-only ingress — 200. Credentials/token values находятся только в EFS private files, в Git/чат/логи не выведены.

Штатный **самостоятельный вход Ивана** на `http://localhost:13041` подтверждён UI меню аккаунта: ivan@ays-connect.ru. Подготовленный immutable ingress не публикует ports; доступ только SSH `127.0.0.1:13041`, production public proxy пока продолжает прежнюю работу. Ingress отображает RC frontend, upstream до deployment — прежний backend. Пароль и roles/grants владельца не менялись, owner tokens не извлекались и не выпускались обходом auth.

### Защита файлов и проверка recovery key

Пользователь назначил **I:\AYS Connect** off-host хранилищем. Новые каталоги создаются с user-only ACL и **EFS до записи raw files**. Проверена реальная EFS encryption (AES-256), не неподтверждённый BitLocker. В `I:\AYS Connect\Objects\snapshot-20261009T0949Z` четыре файла snapshot/digests/age копии, SHA исходных DB/media совпадают. Все 96 файлов прежнего private release evidence и private evidence более раннего O0 snapshot также зашифрованы EFS; исходные bytes сохранены. Release private state/persona credentials в `I:\AYS Connect\Objects\release-220ffac\private`, шифрование наследуется. Full-disk BitLocker **NOT VERIFIED**, не используется как доказательство.

Отдельная физическая key copy: **F:\CodexRecovery\objects-220ffac**, disk 2, user-only ACL, Windows DPAPI CurrentUser. Source identity на C: disk 3, backup destination I: disk 0. Защищённая SSH key copy восстановлена в память/age stdin; **фактическая расшифровка существующего age backup дала исходные DB/media SHA**. Private key не записывался в plaintext temporary file и не включён в архив. Ограничение: все диски на том же Windows host, DPAPI зависит от профиля/master keys текущего пользователя; portable/off-device disaster recovery **не проверен**. Не удалять исходную identity/Windows key material по сроку backup.

Server контур: **LUKS2 / aes-xts-plain64**, новый 2 GiB файл `/home/ivan/ays-objects-rc-065325677b2c/encrypted-storage/storage.luks`, mapper `/dev/mapper/objects-220ffac-recovery`, mount `/home/ivan/ays-objects-rc-065325677b2c/encrypted-storage/mounted`. Ключ случайный 64 bytes, единственная persistent key copy DPAPI на F:, в server filesystem не записан. Восстановленный из DPAPI ключ успешно прошёл `cryptsetup open --test-passphrase`; findmnt доказал encrypted mapper. Для root-only storage preparation использован краткоживущий configured Docker helper без network; production mounts не затрагивались. IPC/udev ожидание первого helper устранено, для последующих helpers используется host IPC; повторный format не выполнялся.

Существующий server snapshot backup перенесён на encrypted mount с сохранением прежнего пути symlink; SHA DB/media прежние. Четыре **остановленных** rehearsal volumes перенесены на encrypted mount с bind к прежним Docker mountpoints: RC pg **4740 files**, media **4**, static **163**, предыдущий O0 pg **4743**. Все file SHA/UID/GID/modes совпали; production DB/media volumes не менялись. Raw `/tmp` двух retained copy API сохранён в encrypted storage, copy API пересозданы с прежними image/commands/environment, read-only rootfs и encrypted /tmp; прежние ephemeral writable layers удалены, **DB records/backup history не удалялись**. После исправления env-file newline передача всех environment values проверена; RC copy check/migrate --check PASS, helpers остановлены.

Это **file/logical-volume at-rest защита Objects backup/rehearsal scope**, не доказательство физического стирания старых plaintext blocks на свободном месте. Free-space remanence **NOT VERIFIED**, wipe/retention не выполнялись. Старый periodic production backup history/daemon не менялся и не принимается как encrypted release storage; новую rollback точку создавать только на проверенном LUKS mount и EFS off-host destination. После reboot unlock/mount и все bind mounts требуют восстановления с ключом recovery owner; **STOP до записи**, если findmnt не указывает mapper. Retained copies не должны стартовать автоматически в отсутствие encrypted mounts.

### Минимальный live scope и обязательное закрытие

Подготовленный сценарий проверен только на изолированной копии: authenticated no-grant detail 404/create 403/list count 0/lookups; затем **только** location.view + location.manage_zones с location scope на маркированном root, list count 1/detail 200/lookup 200/zone create 201, root create вне контекста 403, related People/Tasks/Requests/Projects скрытые counts 0. RoleService revoke → detail 404; EmployeeService terminate → User/Employee inactive, active assignments=0; **старый access/refresh и новый login 401**, global grants=0. Аудит сохранён; это rehearsal, **не production permissions PASS**.

Live применит тот же минимум к разрешённому `RELEASE-SMOKE-220ffac-<UTC>` root; общий role/grants реальных пользователей не трогать. Positive scoped-create здесь — **зона внутри явно разрешённого test parent**. Positive **root-object** scoped-create через LegalEntity — **N/A при отсутствии разрешённого LegalEntity-контекста**, не отмечать PASS и не создавать реальное юрлицо/оргструктуру предположением; попытка вне контекста обязана быть denied. Location permissions не должны давать доступ к People/Work/Requests/Projects: проверить related counts и прямые недоступные реальные records, без новых рабочих связей.

Ровно один root через owner UI, replay без дубля и одна зона; зона создаётся scoped persona. Операции cleanup root/zone выполняет owner, права test role лишь view/manage_zones. Каждое назначение/revoke через RoleService, дополнительно аудит scope/root/expiry и фактическая permission check. Уборка **всегда**, включая STOP: revoke test assignments, deactivate test-only role, EmployeeService terminate для User/Employee, framework SessionStore delete только сессий test user (аудировать), проверить свежий valid access до деактивации и тот же access/refresh/new login 401 после неё. Никаких SQL DELETE или удаления audit/domain rows. Cleanup script и phase state сохранены в защищённом private storage.

Актуальный preflight source после создания persona: **Users 5 / Employees 4**, Work 2, Project 1, Requests 0; восемь целевых справочников отдельно 0. Migrations **101/0/0**, source runtime 407/407, реальные EmployeeRole=1 и global location view/manage по 1. Прежняя O0 acceptance остаётся привязана к snapshot 09:49, новая persona и post-snapshot drift должны войти в **новый frozen baseline/rollback backup**. До нового backup/restore+full-copy-init и GO merge/production init не выполнялись; production readiness **CONDITIONAL**, deployment **NOT PERFORMED на момент этого preflight**. Следующие действия уже разрешены пользователем; повторных разрешений на предусмотренные шаги не требуется.


## 09.10.2026 — production release preflight: STOP ДО MAINTENANCE

Пользователь разрешил merge/release по runbook, но явно запретил считать разрешение принятием пропуска обязательного gate. Recovery owner — **Иван**, хранение 90 дней, удаление только по его решению. Разрешение сохраняется; повторное подтверждение предусмотренных шагов не требуется после устранения конкретных блокеров. До устранения обязательных условий PR #1 остаётся draft/open/unmerged, HEAD RC `220ffac89568a0e7b2aa493a4b599e0aa1946772`; release/merge SHA отсутствует. Production downtime этой попытки **0 секунд**, init/migrations/image switch/новый backup/write-smoke не выполнялись.

Повторный read-only inventory (`transaction_read_only=on`) фактического production: applied migrations **101**, Location/Facility/Zone и Company/Region/Cluster/LegalEntity/OrgUnit отдельно **0**. Users **4** против snapshot **3**, Employees **3** против **2**: имеется drift реальных данных после snapshot 09:49 UTC, перенос прежней acceptance на них запрещён. Role **1**, RolePermission **125**, EmployeeRole **1**; fingerprints всех трёх совпадают с frozen snapshot. Source runtime backend и каждого из шести workers: **407/407** нормализованных tracked Python/requirements hashes совпали с main `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`. В момент preflight все прежние 13 containers/images сохранены: 11 running, 2 exited one-offs; оба HTTPS домена /, live, ready — **6/6 HTTP 200**. Семантический скан новых данных/свежая frozen acceptance ещё не выполнены, прежний O0 PASS остаётся ограничен snapshot 09:49.

Pinned backend/frontend images и production override повторно прошли config/digest/env/command/mount проверки; SHA override прежний. Runtime/schema RC не изменились, документы не требуют image rebuild. Штатный production UI через существующую сессию показывает аккаунт **ivan@ays-connect.ru**, active superuser с active Employee подтверждён read-only. Пароль/roles/grants не менялись, токены не извлекались и не выпускались серверным обходом. Доступ к original-origin UI подтверждён; login/session для **отдельного SSH-only smoke origin ещё NOT VERIFIED**, существующая сессия автоматически между origins не переносится. До downtime необходим реально проверенный штатный вход на smoke origin.

Обязательные STOP-блокеры:

1. **Live scoped/denied persona отсутствует.** Текущие active non-superuser=0, в том числе suitable active Employee persona=0. Есть inactive non-superuser, его не активировали и credentials не использовали. Основной owner superuser непригоден для проверки scoped/denied прав. Анонимно на RC можно проверить отказ без JWT/с невалидным JWT (401), отсутствие анонимного доступа и закрытый admin route (403 на ingress). Это не проверяет authenticated 403/hidden-detail 404/scoped list/detail/lookup/counts, scoped create и доступ к связанным People/Work/Requests/Projects. Эти сценарии подтверждены **только на изолированной копии**; production PASS им не присваивается. Необходима доступная подходящая существующая active persona и штатная авторизация; новое сообщение не является waiver. Новые accounts, activation или grants changes этой попыткой не выполняются.
2. **Защита всех backup/raw/restore storage не доказана.** Повторный Windows BitLocker query не дал успешного status; ACL подтверждает access restriction, не encryption. Server guest topology ext4/LVM без crypt/LUKS слоя, encryption provider storage не подтверждена. Age encrypted copy проверенного 09:49 backup остаётся валидной, но raw source/off-host files, retained earlier evidence и restored PG/media volumes этим не защищены. До maintenance требуется подтверждённое encrypted хранение всего охватываемого raw/restore набора и новых release файлов; старые копии/volumes нельзя удалять без решения Ивана.
3. **Отдельная защищённая key custody отсутствует в доказательствах.** Имеющаяся identity находится на том же Windows устройстве в OneDrive Desktop; независимое защищённое место/доступ recovery owner и контроль восстановления оттуда не подтверждены. Сам факт ключа вне ciphertext archive не закрывает gate. Не копировать private key в backup/repository и не запрашивать его в чате.
4. **Штатная авторизация SSH-only smoke не завершена.** Original-origin session есть; доступного подтверждённого login для отдельного loopback origin пока нет. Подготовить и подтвердить его до write freeze, без передачи password/token в чат, сброса пароля или обхода auth.

Действие по STOP: production остаётся на прежней версии и продолжает обычную работу; maintenance/merge/release не начаты. Исходные dirty-файлы сохраняются. После устранения ресурсов и persona/auth выполнить новый read-only drift review, затем разрешённый цикл fresh freeze/защищённый off-host rollback point/restore/init/smoke/workers/open. Пользовательское разрешение цикла не нужно запрашивать повторно. После новых writes старый backup не восстанавливать вслепую; решение сохранения новых данных и rollback принимает Иван.


## Финальный пакет выпуска RC 220ffac — подготовлен, production не переключён

Evidence O0/upgrade относится строго к frozen snapshot **09.10.2026, 09:49 UTC** (capture 09:49:39.874375–09:49:41.107101 UTC), source main `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`. O0 — PASS; upgrade полного init восстановленной off-host копии — PASS; legacy mapping/перенос — N/A только этому snapshot. Ограничения semantic scan и пустых FileField references из репетиции сохраняются. Эти результаты не доказывают состояние production после возобновления writes.

Перед подготовкой повторно проверен diff четырёх документов против сохранённых reviewed SHA-256: совпадает. `git diff 73a8092b4b0675daf2f0a6ab11fb8e090226f58c 220ffac89568a0e7b2aa493a4b599e0aa1946772 -- backend frontend` содержит только прежний browser-test; substantive working-tree diff backend/frontend пуст. Runtime и схема не менялись. Повтор полного 585 regression не нужен. В этой задаче изменены только четыре документа; CRLF-only views.py и 13 исходных dirty-файлов сохранены побайтово, index пуст.

### Immutable артефакты и override

Все images доступны локально на production Docker host в отдельном staging `/home/ivan/ays-objects-rc-065325677b2c/release-package`; registry push и переключение сервисов не выполнялись. Docker inspect подтверждает разрешение каждого указанного RepoDigest в соответствующий image ID (linux/amd64). `pull_policy: never` исключает незаметную подмену загрузкой; перед выпуском повторить inspect и проверку наличия.

| Артефакт | Проверенный RepoDigest |
|---|---|
| Backend / init / шесть workers, exact RC, 416/416 source hashes | `ays-objects-rc-065325677b2c@sha256:83c65c8816fcff3c09ea37482282edc13397fd67440dba8bb83d0eadfb98ffa6` |
| Frontend, exact git archive RC, VITE_API_URL=/api/v1, VITE_APP_VERSION=full RC | `ays-objects-rc-065325677b2c@sha256:69fe92bab0926f813ea68d2bee60c3746883e876a4eb8ea6108a21251fe3b85f` |
| Test-only ingress, тот же проверенный frontend bundle | `ays-objects-rc-065325677b2c@sha256:ddb5cc4736ea2a96437f33b2add2142d5d47b7caf517127c89b7f15c986d6126` |
| Сохранённый source proxy | `caddy@sha256:af32e97399febea808609119bb21544d0265c58a02836576e32a2d082c262c17` |

`production.override.yml` SHA-256 `00cca67bbd90d850618bfb06538c4a529e84c49ca548e61a64bc304daa2c9560`. `docker compose --env-file /opt/ays-connect/.env.production -p ays-connect-production -f <stage>/source/docker-compose.prod.yml -f <stage>/source/docker-compose.iiko.yml -f <stage>/production.override.yml config --quiet` — PASS. Полный config с секретами не сохранялся/не выводился. Проверены одинаковый backend digest для восьми сервисов, frontend digest, AYS_CONNECT_VERSION, прежние environment values (кроме version), iiko Gunicorn command, реальные volume/network names. Сохранён фактический TLS Caddy bind `/home/ivan/ays-releases/64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85/deployment/Caddyfile.production` (SHA `f60739fcf1e5e5de2f1cf12ff7a2227244b86158a41ae0e4c14204448230ae5c`), а не Git RC HTTP-config.

Ingress Caddy validate — PASS. Через ingress с immutable production-flavoured frontend на уже upgraded изолированной копии выполнен неизменный `objects.spec.ts`: **6/6 PASS**, включая scoped negative persona, idempotency, lifecycle и archive. `/admin/` — 403, anonymous Objects API — 401; опубликованных портов нет, copy network internal=true, source mounts/networks отсутствуют. Исходные строки копии сохранены с ранее оговорённым исключением трёх synthetic number counters; migrate --check — PASS. Helpers остановлены, volumes сохранены. Это artifact acceptance на копии, не production smoke. Подготовка не запускала production init/backup/retention и не меняла production services.

### Фактическая защита backup и согласованные решения

Recovery owner — **пользователь**, разрешение отката/сохранения новых данных даёт он. Backup, защищённые копии и rehearsal volumes хранить **90 дней**; удаление только по отдельному разрешению пользователя, без автоматического удаления по истечении срока. Для snapshot 09:49 минимальная дата — **07.01.2027 09:49:41 UTC**; для свежего release backup срок отсчитывается заново. Не менять periodic production retention в этой задаче; release evidence хранится вне его назначения.

Windows ACL off-host directory — user-only; BitLocker подтвердить не удалось, **NOT VERIFIED**. Server файлы 0600 / directory 0700, filesystem ext4 на LVM; guest lsblk не содержит crypt/LUKS слоя. ACL/mode не являются доказательством шифрования. Шифрование хоста провайдера не проверено. Исходные database.dump/media.tar.gz и восстановленные volumes остаются без подтверждённой at-rest encryption.

Доступный вариант проверен фактически: official **age v1.3.2**, Windows release ZIP SHA подтверждён GitHub release metadata. Создана отдельная encrypted copy **существующего** snapshot, без нового production backup: private `snapshot-20261009T0949Z.tar.age`, SHA `477d3dcc4e3338ebf305d82b9c01ad6fa73293cd855980c2fcdc2bdfb7657df0`. Расшифрование в память дало исходные SHA DB/media; tamper rejection — PASS. Recipient — public key существующей SSH identity, private key не включён в архив. [age поддерживает SSH-ed25519 identities](https://github.com/FiloSottile/age/blob/main/README.md). Ключ сейчас на том же Windows устройстве (OneDrive Desktop): независимая защищённая key custody **не доказана**. Ciphertext защищён на уровне файла, но общая защита всех raw копий этим не закрыта. Исходные файлы не удалялись.

До GO обеспечить cipher-only хранение нового rollback DB/media point (потоковое шифрование до записи archive на persistent storage, отдельные plaintext/ciphertext checksums, явная проверка pipe exit codes), доступность ключа recovery owner через защищённый отдельный канал и восстановление именно из off-host ciphertext. В isolated restore plaintext PG/media volumes защищать реально подтверждённым encrypted storage; иначе отдельно принять ограничение, не заявлять at-rest gate PASS. Не уничтожать старые raw copies без разрешения пользователя.

### Restricted smoke — согласованный сценарий, запуск не выполнен

P1 — существующий active superuser с active Employee; пользователь согласовал выполнение оператором через собственный логин. Соответствие аккаунту хранится только в private `smoke-persona-candidates.private.json`. Перед окном проверить актуальные flags/Employee/grants read-only. Не создавать/активировать accounts, не менять пароли или grants. P1 проверяет позитивный путь; superuser не доказывает scoped permissions. В snapshot нет active non-superuser/denied persona. **Оставшееся решение пользователя:** предоставить существующую подходящую persona для live scoped/denied проверки либо явно согласовать это ограничение выпуска, опираясь на изолированные tests. Сейчас live scoped acceptance не закрыт.

Ingress запускать только в разрешённом release window, при публичном proxy и writers закрытых. Отдельный контейнер exact ingress digest в production network, read-only rootfs, tmpfs /data,/config, static volume read-only; **без -p**, без media route, `/admin/*` запрещён. SSH tunnel с локальным bind `127.0.0.1:<port>` к private IP ingress:8080; operator browser открывает loopback. Upstream `backend:8000`, Host localhost/X-Forwarded-Proto https; доступ к серверу только настроенной SSH identity. Production network само по себе не internal (имя не доказательство), поэтому отсутствие public published ports и private SSH path проверять фактически. Подготовленный config уже проверен на copy; production ingress в этой задаче не запускался.

1. UI exact bundle: создать один `RELEASE-SMOKE-220ffac-<UTC>` объект, office / Asia/Novosibirsk / preparation. Не создавать LE/OrgUnit и не переводить в operating без действующего необходимого контекста. Сохранить payload/key/UUID в private журнале. Идентичный replay — тот же UUID (201 затем 200), изменённый payload с тем же key — 409, без второго Domain Audit/Outbox.
2. Создать ровно одну `<marker>-ZONE`, каждый раз брать текущую version. Проверить list/detail/tree/lookup/counts, parent UUID/version и related People/Work/Requests/Projects read-only. Anonymous — 401; scoped/denied проверки только согласованной существующей persona. Legacy Location writes — 405, Django Admin ограничения — по ранее принятому code/copy evidence: production admin ingress закрыт.
3. Уборка domain API/UI: archive zone → close root с reason `release smoke completed` → archive root. Между действиями GET current version. Проверить запрет новой зоны под archived root (400, ноль записей). Не DELETE/SQL cleanup; UUID, код и история сохраняются.
4. Допустимые domain writes: два Location, один LocationIdempotency, пять соответствующих событий Audit/Outbox: location.created, location.zone_created, location.archive(zone), location.close(root), location.archive(root). Также обычные auth/session/JWT artifacts существующего логина и необходимые технические служебные записи; отдельно зарегистрировать фактический delta. Ни User/Employee/grants, ни responsibilities/assignments, ни реальных задач/обращений/проектов не создавать. Replay/conflict/failed archived create не добавляют domain events. Непредусмотренный delta — STOP. Workers пока не запускаются.

### Выпуск: обязательные GO / STOP и следующее разрешение

Ниже — подготовленный порядок, **не выполненные production команды**. Существующий раздел runbook ниже даёт backup/init/rollback детали; этот package section уточняет immutable images, SSH-only ingress, решения владельца и at-rest ограничения.

1. **GO preflight:** repeat read-only drift/source hashes/applied migrations/counts/grants/persona checks, место, tools, immutable refs/override, off-host destination и ключ восстановления. Snapshot 09:49 не переносить на новые данные. Неизвестный drift/legacy или отсутствующий ресурс — STOP до downtime; повторить необходимую isolated acceptance.
2. **GO write freeze:** новое согласованное окно; зафиксировать текущие IDs/images/states/config. Закрыть public proxy, остановить backend/шесть writers после завершения jobs; periodic backup pause, не restart/retention. Подтвердить отсутствие внешних writers, in-flight/prepared transactions. Иначе STOP и resume старых IDs.
3. **GO rollback point:** свежий согласованный DB/media после возобновлённых writes, уникальные имена без перезаписи/retention, подтверждённая encryption, plaintext/ciphertext SHA. Off-host transfer/checksum, decrypt/restore из этих off-host файлов в новые isolated encrypted volumes с egress blocked/no workers/source mounts. Сверить current frozen business/grant/media fingerprints и ожидаемый plan. При необходимости долгой репетиции сначала возобновить старый production; затем новое freeze и новая актуальная точка, если writes изменились. Нельзя использовать устаревшую точку как fresh.
4. **GO init:** только после gates 1–3 и отдельного разрешения, ровно один `dc run --rm --no-deps init` с backend digest. Ожидаемые пять migrations перечислены ниже; migrate+seed_permissions+collectstatic+chown. Повторный plan пуст, check/drift/RBAC/business/media сохранены. Unexpected plan/privilege/data delta либо partial init failure — STOP, не повторять init вслепую.
5. **GO restricted smoke:** `dc run --rm --no-deps frontend_assets`, затем `dc up -d --no-deps --no-build --force-recreate backend` с pin. Public proxy закрыт; SSH-only ingress+согласованные personas, сценарий выше и archive cleanup. Проверить image/version, health/ready/media/legacy consumers, событийный delta. Scoped gate должен быть закрыт persona или явно принят owner как ограничение. При failure — STOP/write freeze.
6. **GO writers:** заменить/запустить ровно шесть workers с тем же backend digest (`--no-deps --no-build`); проверить health/heartbeats, Outbox pending/failed/repeated и внешние effects. С этого момента возможны новые реальные записи/доставки даже при закрытом proxy. Непредусмотренная доставка/дубли/сбой — STOP.
7. **GO users:** убрать test-only ingress, проверить старый сохранённый TLS config и HTTPS/live/ready/SPA при restricted доступе; открыть пользовательский ingress только после всех проверок. Согласованно resume periodic backup без немедленного retention release point. Записать UTC открытия и actual deployed IDs/digests. До этого deployment не считается завершённым.

**Откат:** до init вернуть сохранённые старые IDs без зависимостей. После init schema compatibility старого кода не предполагается; reverse migrations автоматически не выполнять. При rollback восстановить fresh off-host backup в новые volumes, не поверх рабочей БД, сохранить изменённый контур/evidence. Потерю даже разрешённых smoke/auth/Audit/Outbox записей разрешает только recovery owner. После workers/user writes старый backup **нельзя восстанавливать вслепую**: снова freeze, защищённая аварийная копия текущего состояния по разрешению, полный delta новых записей/media/external effects, план сохранения/replay/forward fix и решение пользователя. Внешняя доставка restore не отменяется.

**Точный объём следующего разрешения:** maintenance/freeze и актуальный защищённый rollback DB/media backup, off-host verification+isolated restore, применение указанного init/пяти migrations и exact images, SSH-only P1 smoke (один объект/зона, архивирование, только перечисленные effects), запуск workers/проверка Outbox и открытие доступа при GO. Не включать создание accounts/grants, legacy классификацию/перенос, blind restore/потерю новых записей. Commit/push/merge отдельно этим пакетом не разрешены. При STOP возврат прежнего контура до init допускается по runbook; после data-changing действий решение об откате принимает пользователь.

Итог: **release package подготовлен; production readiness CONDITIONAL; deployment NOT PERFORMED**. Остаточные gates: актуальный drift/fresh rollback point/off-host restore, доказанная защита всех release backup/restore storage и независимая key custody, решение по live denied/scoped persona, отдельно разрешённые production init/smoke/workers/open и последующая фактическая проверка.


## 09.10.2026 — предрелизная backup / full-init репетиция RC 220ffac

**O0 frozen snapshot — PASS; согласованный DB/media backup, off-host checksum и independent restore — PASS; полный фактический init RC и upgrade — PASS; API 32/32 и browser 6/6 — PASS. Legacy mapping / перенос — N/A только для этого snapshot. Production readiness — CONDITIONAL; deployment и production write-smoke — NOT PERFORMED.**

Разрешение этой задачи: кратко закрыть пользовательский доступ, остановить writers, подготовить свежий согласованный backup и восстановить off-host файлы в новом isolated contour. Production init/migrate, изменение рабочей схемы/данных/accounts/grants, merge, commit, push и deployment не разрешены и не выполнялись. После off-host проверки прежний production возобновлён **до** изолированной репетиции.

### RC и актуальный source drift

RC `220ffac89568a0e7b2aa493a4b599e0aa1946772`, branch `codex/objects`, [draft PR #1](https://github.com/JohnyRiddle/ays_connect/pull/1). `git diff --name-only 73a8092b4b0675daf2f0a6ab11fb8e090226f58c 220ffac89568a0e7b2aa493a4b599e0aa1946772` содержит только шесть документов и browser-test: runtime/schema неизменны. Текущий browser-test raw SHA `0d19dad80147e1dbe658db52842ee84f32a5ca287f30f12574c8c3f5195facc9`, обе URL assertions сохранены. Полный 585 regression не повторялся; его evidence от 08.10 относится к неизменному runtime. Новые API/browser результаты ниже относятся к **свежей** восстановленной копии после **полного init**, не к прежнему online dump.

Фактический production project `ays-connect-production`, working directory из labels `/home/ivan/ays-releases/64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`, Compose prod + iiko из этой директории; настроенный environment file `/opt/ays-connect/.env.production`. Содержимое env/identity/credentials не выводилось. Backend container/image прежние: `f66b6b84e6bb5f9b032183635a0ed7149487dc902fdf8858d7ee4f36287bbbb2` / `sha256:182f57f5ad5340e055edf113e66ab4ce7886a0995c48b324bcb826224d6e9b6f`.

Read-only source inventory через установленный production Django runtime и прежние PGOPTIONS: PostgreSQL **17.11**, applied/pending/unknown **101/0/0**. Backend и **каждый из шести workers** совпали с main `64f85fa…` по **407/407** Python/requirements files. Images workers различны, их фактические IDs зафиксированы отдельно, равенство images не предполагается. Все 13 containers/images/commands/mounts/states сохранены в private evidence; 11 running и 2 exited one-offs (init/frontend_assets). Возобновление сохранило эти IDs/images и running/exited states, one-offs не запускались.

Актуальные counts отдельно: **Location=0; Facility=0; Zone=0; Company=0; Region=0; Cluster=0; LegalEntity=0; OrgUnit=0**. FK fields **71**, все reference counts=0, errors=0. Source Users=3, Employees=2, Work Task=2, Project=1, ServiceRequest=0, iiko KnownGuest=2, CardCreation=0. Global location.view=1, global location.manage=1, EmployeeRole=1. После возобновления source снова 101/0/0 и все восемь counts=0; fingerprints Users/Employees/Role/RolePermission/EmployeeRole совпали с frozen baseline.

Fresh semantic scan этого snapshot: **505 fields / 5477 nonempty values**, включая 39 пустых JSON containers. Явных **непустых** object ID/key references=0; два location_id keys в Outbox имеют null и не являются mapping candidates. Audit object references=0; GenericForeignKey fields=0. Значения и ПДн не выводились. Ограничение неизменно: encoded/name-only/произвольные свободные ссылки автоматический скан не исключает. Empty legacy N/A доказан рабочими таблицами этого backup; искусственные legacy строки, классификация и перенос не создавались.

### Preflight, write freeze и возобновление

До downtime проверены strict known-host SSH, Docker 29.7.2, tar/sha256sum, pg_dump/pg_restore 17.11, Edge/Playwright, место (~35 GB server / ~105 GB off-host при preflight), mode 0700 нового server directory и off-host ACL только текущего пользователя вне Git/OneDrive. Собран отдельный RC backend image **`sha256:83c65c8816fcff3c09ea37482282edc13397fd67440dba8bb83d0eadfb98ffa6`**; все **416/416** RC Python/requirements files совпали с git archive exact RC. До downtime подготовлены inert capture container, новая internal network, пустые PG/media/static volumes и inert RC API. Это rehearsal artifact; production image override/frontend image этим не принимаются.

Проверены host timers, cron.d и cron spool без вывода содержимого заданий: AYS/Docker/DB backup jobs вне известного backup container не обнаружены; production DB/Redis не публикуют ports, публичный ingress только proxy. Periodic backup container находился в sleep 86400 без pg_dump/tar. Вместо stop/start применён **pause/unpause того же ID**: остановлен таймер/retention и сохранено прежнее ожидание; restart старого loop немедленно вызвал бы backup.sh/retention. Старые backup SHA до/после совпали, удаления/retention и перезаписи не было.

Proxy и backend остановлены по сохранённым IDs с timeout 330s. Worker PID1 shell не передаёт TERM sleep; только после завершения Python jobs безопасно завершены idle sleep, затем подтверждено exited состояние всех шести workers. Busy job не прерывался; завершающий helper может получить exit 137 при остановке namespace, это не считается доказательством завершения job без inspect. После всех остановок **other client connections=0, in-flight transactions=0, prepared transactions=0**. DB/Redis продолжали работать. Для resume использован `docker start` сохранённых backend/worker/proxy IDs, не Compose dependency traversal; backup unpause.

| Событие | UTC 09.10.2026 |
|---|---|
| Начало maintenance операции | 09:47:03.146947 |
| Proxy stopped (Docker FinishedAt) | 09:47:04.101417879 |
| Write freeze / нулевые in-flight подтверждены | 09:49:37.825392 |
| Frozen row baseline сохранён | 09:49:39.874375 |
| Начало DB/media capture command | 09:49:39.874375 |
| Окончание capture command | 09:49:41.107101 |
| Off-host SHA проверены | 09:49:43.696577 |
| Прежний proxy started (Docker StartedAt) | 09:50:17.798340263 |
| Все внешние HTTPS проверки завершены | 09:50:24.749291 |

**Proxy stopped interval — 193.697s (3 min 13.7s); вся maintenance операция до финальных проверок — 201.602s (3 min 21.6s).** Время недоступности HTTPS ограничено сверху 200.648s от FinishedAt до завершения проверок; мгновенная готовность TLS в StartedAt не предполагается. Snapshot идентифицирован ниже dump SHA и frozen capture window; отдельный timestamp открытия pg_dump transaction не измерялся.

До открытия proxy backend ready=200 и все семь writer containers healthy. После открытия `https://ays-connect.ru` и `https://www.ays-connect.ru`: `/`, `/api/v1/health/live/`, `/api/v1/health/ready/` — **200** с проверкой TLS. Старые DB/Redis/backup и workers работают; после остановки rehearsal production снова проверен **2026-10-09T10:15:06.022180+00:00**: прежние IDs/images/states, HTTPS/health PASS. Production schema/RBAC/data mutation commands и write-smoke не выполнялись; обычная работа прежних workers после resume разрешена и может создавать новые записи.

### Новый backup / off-host / independent restore

Уникальный server directory `/home/ivan/ays-objects-rc-065325677b2c/backup`, без прежних production backup mounts для записи. Read-only production media mount использовался только inert capture helper, после получения файлов helper остановлен. `backup.sh`, retention, DROP DATABASE и существующие restore scripts не запускались.

Защищённое off-host назначение **`C:/Users/riddl/.codex/private/objects-release-85aee147f94841ba8aafadafca64b5ec`**: вне OneDrive/Git, inheritance удалён, ACL текущего пользователя; транспорт SSH с known-host проверкой. Source/off-host SHA256SUMS совпали:

| Файл | Bytes | SHA-256 |
|---|---:|---|
| database.dump | 1 024 851 | `df1943c4e0286cb1d0cfe55ade14ce636187138134f137d1c0d1e9762c777504` |
| media.tar.gz | 398 | `63e15ba15ac544c6de0d349438e999d5025d7b1ff3accf7bf1e89577f4225d63` |

Archive listing проверен; media members только относительные media/ paths, без traversal/links/devices. Перед restore SHA повторно проверены. Обе БД **objects_copy и objects_original** восстановлены `pg_restore --exit-on-error --no-owner --no-acl` из **локального off-host database.dump через SSH stdin**, media — из **локального off-host media.tar.gz**, не из server-local backup. DB owner/ACL адаптированы к новой isolated роли; production roles/grants не менялись.

Новый project **ays-objects-rc-065325677b2c**: network `-net` internal=true, volumes `-pg`, `-media`, `-static`, containers `-db` / `-api`. Нет published ports, production mounts/networks и production runtime env, restored workers/cron; SMTP/Telegram/iiko disabled, signing secret и DB password новые. Из copy TCP к 1.1.1.1:443 и 109.237.109.58:443 блокирован. SSH loopback tunnel даёт только локальный доступ к copy API. Инертный capture helper с разрешённым source read-only mount остановлен до репетиции и не относится к восстановленным DB/API mounts.

Оба restore до init: **196 tables / 1950 rows**, все fingerprints совпали с frozen source. Independent objects_original осталась неизменной и после всех тестов. Media **4 files / 40 content bytes**, все hashes совпали до/после init/tests, app имеет права чтения; реальных FileField references в snapshot **0**, missing=0. Это подтверждает перенос фактического архива, но не функциональность отсутствующих пользовательских attachments. Off-host ACL/SSH защита подтверждена; статус BitLocker/at-rest encryption не удалось прочесть без administrative rights (`manage-bde -status C:`: access denied). Политика долговременного хранения, at-rest защиты и recovery owner требуют согласования для выпуска; этот отчёт не утверждает encrypted-at-rest backup.

### Полный actual init и acceptance свежей копии

Ordered migration plan до init ровно пять entries, как в runbook ниже; approved plan SHA-256 (UTF-8 lines, final LF) **`ff6526d3ca8a01154ebe65465a60f81340f972be1cea90b1c3dcc34311834baf`**. Actual init command сверена с exact RC Compose и выполнена **один раз только в copy**, user 0:0:

```sh
python manage.py migrate --noinput && python manage.py seed_permissions && python manage.py collectstatic --noinput && chown -R app:app /app/media /app/staticfiles
```

Full init started **2026-10-09T09:53:41.065071+00:00**, finished **2026-10-09T09:53:50.900860+00:00**. Exit **0**: пять migrations OK, `Permissions ready: 162`, **163 static files** собраны и доступны app. Это PASS полного init, включая seed_permissions/collectstatic/chown, который прежний online-snapshot отчёт не проверял. Copy runserver для browser работал от **app**, не root.

После init: **198 tables / 1973 rows**, **192 исходные таблицы fingerprints unchanged**. Только ожидаемые deltas: access_control_permission **166→174**, auth_permission **740→748**, django_content_type **185→187**, django_migrations **101→106**; две новые Organizations tables пусты. Все старые catalog identities/rows сохранены; seed_permissions существующие labels не изменил (**renamed=0**). Role, RolePermission, EmployeeRole, User privileges/passwords и Employee fingerprints неизменны; новые grants реальным пользователям отсутствуют. Старые business sequences unchanged; изменились только auth_permission/django_content_type/django_migrations sequences вслед за catalog additions. Все восемь справочников после init ещё пусты, автоматической классификации/legacy insertion/backfill нет.

`MigrationExecutor` повторный plan **[]**, `check` **0 issues**, `migrate --check` PASS, `makemigrations --check --dry-run` **No changes detected**. После tests повторный plan [] / applied=106.

- **32/32 ObjectsTests methods**, **19.078s**, каждая проверка в atomic rollback на objects_copy без test DB/flush: create/replay/conflict/scopes/list/detail/lookups/counts, lifecycle/zones/responsibles, Audit/Outbox, old API/Admin/ORM bypass, bindings/related policies. Четыре concurrency tests не повторялись: их PASS — прежний PostgreSQL 585 checkpoint на неизменном runtime.
- Новая non-superuser persona с **125** cloned grants существующей роли: capability/create/replay PASS; исходная роль и реальные accounts не менялись. В atomic rollback новая test-admin persona прочитала исходные **2 Work / 1 Project**, status 200; это не обещает доступ всем существующим scoped ролям.
- **Browser 6/6 PASS, 29.5s, exit 0** на fresh full-init copy, exact RC test SHA выше; Edge/Playwright, loopback UI13031/API18081, прежний final frontend build index-DwZChlut.js / index-BBC6vgjQ.css. Все assertions поведения и две URL assertions сохранены; ошибок/ожиданий не подавляли. Fixtures прочитаны UTF-8, созданы только новые copy synthetic accounts/records.
- После acceptance все исходные строки сохранены; только три source number-counter rows в employees_employeenumbersequence, projects_projectnumbersequence, work_tasks_tasknumbersequence изменились от тестовых созданий. Это **тестовые эффекты в копии**, не миграции или production mutations. Media hashes и independent original restore unchanged.

API/DB/capture rehearsal containers и local SSH/UI helpers после проверки остановлены; новые volumes, RC image и оба backup экземпляра сохранены. Private evidence хранит команды, stdout/stderr init/API/browser, hashes, row/sequence preservation, media manifest, IDs/states, исходный/последующий read-only inventory. В Git нет dump/media/ключей/env/PII. Исходные 13 dirty-файлов и raw CRLF-only views.py проверены побайтово; staging/HEAD не изменяются этой задачей.

### Конкретный следующий выпуск — только по отдельному разрешению

1. Утвердить окно, release/recovery owner, test personas/допустимые smoke effects, защищённое долговременное off-host хранение (включая применимую at-rest policy), ingress allowlist и условия rollback. **Merge/deploy/init/write-smoke требуют отдельного разрешения.** Текущий draft PR не merged; фиксировать exact RC SHA либо отдельно пересмотренный итоговый merge SHA.
2. Подготовить отдельный clean release root для exact RC, сохранив старый root `64f85fa…`, env wiring `/opt/ays-connect/.env.production` и iiko overlay. Собрать **frontend Dockerfile.prod** с VITE_API_URL=/api/v1 и VITE_APP_VERSION=exact RC; зафиксировать immutable frontend image и bundle hashes. Для init/backend/шести workers проверить один approved backend image ID/digest (rehearsal 83c65c… уже соответствует 416 source files); подготовить image override, `config --quiet`, inspect каждого image. Проверенный loopback UI build не выдавать за production bundle acceptance.
3. Заново read-only проверить source/image/migrations/counts/refs/grants **после возобновления production**. Новые legacy/scopes/schema drift — STOP, новая inventory/mapping/upgrade acceptance. Обычные новые Work/Projects требуют fresh preservation baseline. Этот backup 09:49 UTC нельзя использовать как гарантированно актуальную release rollback точку после новых writes.
4. В новом согласованном write window закрыть ingress, корректно завершить writers (idle-worker helper ниже), приостановить sleeping backup timer без retention, подтвердить in-flight/prepared=0. Создать **новый** согласованный DB/media backup, source/off-host SHA match и independent restore proof. Сохранить исходные IDs/images/states. При ошибке **до init** вернуть старые IDs, проверить workers/health/HTTPS и открыть прежний доступ; не применять RC. Длительную новую data rehearsal снова проводить с возобновлённым прежним production, затем согласовать новую актуальную rollback точку перед выпуском.
5. Пока writes закрыты и свежий reviewed plan ровно ожидаемые пять additions, **один** `dc run --rm --no-deps init` из approved backend image; сравнить output, повторный пустой plan/check/RBAC/business/media. Не повторять partial init вслепую. Затем `frontend_assets --no-deps`, заменить только backend approved image без зависимости на init/assets. Workers пока stopped. Test-only ingress — доказанный allowlist либо операторский loopback tunnel, общий proxy закрыт.
6. **Отдельно авторизованный** create/replay/conflict/zone/rights/Audit/Outbox smoke с согласованными personas, ключом и маркированными объектом/зоной; read-only People/Work/Requests/Projects и media/HTTPS smoke, без произвольных real-account/LE/grant изменений. Только после PASS запустить шесть approved-image workers, проверить heartbeats/Outbox/integrations, затем открыть public writes. Зафиксировать момент первых новых writes/deliveries и отдельно согласовать backup/retention resume с сохранением rollback point.
7. STOP/rollback по разделу 7 ниже: до init resume old IDs; после migrations code-only rollback **не доказан**. По умолчанию restore свежего pre-release DB/media в **новые** volumes после отдельного решения recovery owner, сохраняя изменённые. После реальных новых writes/deliveries **никакого blind restore**: freeze, разрешённая emergency copy/current delta, preservation/replay или forward fix; reverse migrations/DROP/удаление текущих volumes не выполнять.

**Остаются:** отдельное разрешение выпуска/merge/production init/write-smoke; immutable frontend artifact + проверенный production image override/config; работающий test-only ingress и согласованные personas; актуальная на момент выпуска drift/inventory/RBAC и свежая rollback DB/media точка после возобновлённых writes; off-host retention/at-rest/recovery policy; actual production smoke/HTTPS/workers/Outbox и rollback решение для новых записей. Выполненная репетиция закрыла backup/restore/full-init gates **для указанного frozen snapshot**, не все release gates и не deployment.

## История: online DB snapshot и upgrade до полного init, 06:53 UTC

Следующие разделы до release runbook сохраняют прежнее evidence без переименования snapshot. Их указания о ещё невыполненном maintenance backup/full init относятся к прежней задаче; текущие результаты и остаточные условия — выше.

**O0 inventory — PASS для подтверждённого рабочего snapshot. Upgrade / сохранность — PASS. Legacy mapping и перенос — N/A: Facility=0, Zone=0. Production readiness — CONDITIONAL / NOT VERIFIED; deployment — NOT PERFORMED.**

### Точная версия

Runtime checkpoint `73a8092b4b0675daf2f0a6ab11fb8e090226f58c`, ветка `codex/objects`; draft [PR #1](https://github.com/JohnyRiddle/ays_connect/pull/1), main/base `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`, 46 checkpoint files. Перед работой все 36 raw SHA совпали с [manifest](OBJECTS_CHECKPOINT.md).

Release candidate: отдельный commit `docs(objects): record production snapshot upgrade acceptance`, дочерний к этому checkpoint, включает **пять обновлённых документов, этот новый readiness/runbook и две дополнительные assertions ожидания URL в frontend/tests/e2e/objects.spec.ts**. Его точный SHA — commit, содержащий этот документ (PR head после публикации); self-referencing SHA в файл не записывается. Runtime backend/UI и миграции не менялись. Browser-test raw SHA `0d19dad80147e1dbe658db52842ee84f32a5ca287f30f12574c8c3f5195facc9`; текущий fingerprint тех же 36 source paths `0f46cef8e73087a60357c6b44ab6b519d65935475f7c1eaf47208f6ea4acf09a`. Старый manifest остаётся историческим manifest checkpoint; единственное объяснённое source расхождение — browser test.

Code/synthetic acceptance — PASS: runtime regression 08.10 PostgreSQL 585/585 (Objects 36, concurrency 4), inventory 8/8, frontend build/check/drift/install/upgrade/restore PASS. Полный gate не повторялся: общие services/permissions/schema и runtime UI не менялись. Изменённый browser test повторно проверен 6/6 на восстановленной рабочей копии; PASS относится к окончательному локальному diff.

### Подтверждённый источник

Работающий `ays-connect-production` на документированном `109.237.109.58:40222`, `/opt/ays-connect`. Пользователь предоставил существующий SSH identity; подключение с BatchMode/IdentitiesOnly/StrictHostKeyChecking прошло. Содержимое ключа, env и credentials не выводилось. Предыдущие отказы default/deploy identity — исторические, DATA BLOCKED снят для этого источника.

Источник инвентаризации — соединение установленного backend: host `db`, database `ays_connect`, PostgreSQL **17.11**, READ ONLY / REPEATABLE READ. Проверены statement_timeout=60s, lock_timeout=5s; idle timeout=60s задан через PGOPTIONS. Source runtime сверил восемь моделей со схемой до чтения: missing columns/tables=0. Новые Objects модели к production не подключались.

Backend container ID `f66b6b84e6bb5f9b032183635a0ed7149487dc902fdf8858d7ee4f36287bbbb2`; image `sha256:182f57f5ad5340e055edf113e66ab4ce7886a0995c48b324bcb826224d6e9b6f`. **407/407** Python/requirements исходников runtime после нормализации CRLF совпали с main `64f85fa…`; normalized runtime fingerprint `eda2c4df1eb9f2af4cd3ded73fb57276e22289d07e0f1a064cc7bfb1fb8df1b8`. Это доказательство backend версии по source и image, а не одному health marker; полнота совпадения всего frontend deployment этим сравнением не утверждается.

Source applied migrations **101**, pending **0**, unknown **0**. Релевантные cutoffs: organizations 0003; access_control 0002; accounts 0003; employees 0015; work_tasks 0004; projects 0008; iiko 0007. В конце source по-прежнему имел 101 applied migrations и нулевые counts всех восьми моделей.

Статический `o0_status` инвентаризатора остаётся `BLOCKED_PENDING_DATA_PROVENANCE_AND_MAPPING_CONFIRMATION`: сам скрипт не подтверждает provenance и бизнес-решения. Итоговый PASS здесь — отдельное заключение после подтверждения источника, source fingerprints, свежего dump и доказанного empty legacy; не автоматический PASS по exit 0.

Fresh `pg_dump --format=custom --no-owner --no-acl` streamed по SSH в новый защищённый каталог **вне Git/OneDrive** с ACL текущего пользователя. Получение dump завершено **2026-10-09T06:53:54.581111+00:00**, размер **1 024 854 bytes**, SHA-256 `041c5fc9f2e6b7dd14b4c78909d50dd27afb6ff8d0e0f0a54126444816c3521b`. Это timestamp завершения получения артефакта, а не отдельно измеренное время открытия PostgreSQL snapshot: время открытия транзакции pg_dump не записано. O0 PASS относится к source snapshot/этому dump SHA и прочтениям 09.10, не к произвольному будущему состоянию production. Это online согласованный DB snapshot, не maintenance DB/media release backup. Исторический backup 10.09 не использовался. Исходный dump не изменялся.

### Инвентаризация актуального snapshot

| Модель | Count | Пустые поля / дубли / дерево / связи |
|---|---:|---|
| Location | 0 | Пустые/unknown types, коды, родители, активные потомки, LE и OrgUnit — N/A: строк нет |
| Facility | 0 | Legacy mapping N/A |
| Zone | 0 | Legacy mapping и zone/root mismatch N/A |
| Company | 0 | N/A |
| Region | 0 | N/A |
| Cluster | 0 | N/A |
| LegalEntity | 0 | Действующие мультиюридические исключения N/A |
| OrgUnit | 0 | N/A |

Все целевые FK counts равны 0; обнаружено 71 FK field, errors=0. В этой БД есть Users=3, Employees=2, Work Task=2, Project=1, ServiceRequest=0, iiko KnownGuest=2, CardCreation=0. Эти агрегаты не раскрывают имён или содержимого.

Реальные grants: один global location.view и один global location.manage, одна EmployeeRole. Роли/аккаунты production не менялись. В копии проверен новый тестовый пользователь с 125 grants существующей роли: capabilities/create/replay PASS, права не назначались реальным пользователям. Также проверены scoped/denied personas; назначения ответственности не выдают прав.

На исходной восстановленной версии в READ ONLY просмотрено **505** JSON/string/text полей, **5477** непустых значений. Явных объектных ключей/ID/UUID-паттернов — **0**, audit object references — **0**, GenericForeignKey fields — **0**. Ни значения, ни ПДн в stdout/Git не выведены. Ограничение: автоматический скан не доказывает отсутствие произвольных encoded/name-only ссылок; нет существующих целевых объектов, с которыми их можно сопоставить. Свободные тексты не считаются основанием CREATE_NEW. Кандидатов реального mapping нет по причине отсутствия legacy, а не из-за неподтверждённого matching.

### Изолированная копия и upgrade

Выделенный Docker contour/project label `ays-objects-o0-b5d1348f6936`, новые `-net` (**internal=true**) и `-pg` volume; DB/API containers `-db` / `-api`. Существующие DB/volumes не удалялись и не перезаписывались. Docker CLI использован вместо Compose init: ни bootstrap, ни workers не запускались. Базы `objects_copy` и отдельно `objects_original` созданы с новыми именами. Нет public ports, production network/Redis/media mounts и внешнего выхода. Временный signing secret и DB credentials новые; restored sessions не открыты наружу. Исходный image использован только как dependency runtime; `git archive HEAD backend` скопирован в отдельный inert API container, production code не заменялся.

Baseline до подготовки любых тестовых personas: **196 таблиц / 1950 строк**, защищённые SHA каждого table JSON-row set. План содержал ровно:

```text
access_control.0003_alter_rolepermission_scope
organizations.0004_location_address_location_business_status_and_more
organizations.0005_objects_guards_and_permissions
organizations.0006_responsibility_service_guard
organizations.0007_binding_lifecycle_guards
```

После upgrade: **198 таблиц / 1973 строки**. 192 исходных таблицы совпали побайтово по row fingerprints. Допустимые служебные изменения:

| Таблица | До | После |
|---|---:|---:|
| access_control_permission | 166 | 174 |
| auth_permission | 740 | 748 |
| django_content_type | 185 | 187 |
| django_migrations | 101 | 106 |

Новые таблицы — organizations_locationidempotency и organizations_locationresponsibility; добавлены Objects fields/sequence/triggers. RolePermission и EmployeeRole fingerprints совпали; новые grants не появились. Legacy таблицы остались. UUID/code/free types/FK не изменялись; старых Location нет, поэтому сохранность непустых Location значений здесь N/A, отдельно доказана synthetic upgrade fixture.

`check`: 0 issues; `migrate --check`: PASS; `makemigrations --check --dry-run`: No changes detected; повторный migration plan пуст. Исходный dump независимо восстановлен в **objects_original**: все 196 tables / 1950 rows и их fingerprints совпали с baseline. Upgraded dump не подменяет этот restore proof.

### Проверки на восстановленной структуре

- **32/32** ObjectsTests methods выполнены внутри отдельных atomic rollback на objects_copy, без Django test DB/flush. Новые test accounts/records откатились; concurrency 4 здесь не повторялись, их evidence — checkpoint 585 gate.
- Проверены create/idempotency/payload conflict, scopes/list/detail/lookup/counts, hidden related data, Audit/Outbox rollback, версии/дерево/циклы, зоны/ответственные/lifecycle, старый API/Admin/ORM bypass, archive bindings и Work/Requests/Projects policies.
- Новая test persona с grants существующей роли: create/replay PASS без superuser bypass. Исходные 2 Work и 1 Project после upgrade доступны отдельной маркированной test-admin persona. Исходные строки этих consumers и их relationships сохранились. Это не обещание доступности всех проектов любой роли; текущие policies и персональные scopes сохраняются.
- **Browser 6/6 PASS, 29.9s, exit 0**, desktop/mobile, на upgraded copy: existing final build index-DwZChlut.js / index-BBC6vgjQ.css; локальный Edge Chromium, Playwright, UI loopback 13031, API через SSH loopback tunnel 18081 к internal API. Tests используют только новые synthetic accounts. Email/Telegram/iiko отключены; external network blocked; restored Outbox workers не запускались.
- Первые browser attempts не PASS: UTF-8 fixture первоначально прочитан Windows default encoding; исправлены исключительно новые тестовые labels. В browser test выявлено раннее чтение URL до React navigation: добавлено ожидание pathname UUID в двух местах, допустим query `created=1`. Последний полный 6-test run относится к этому окончательному diff. Runtime модуль не исправлялся: дефект был в тестовой синхронизации.
- После тестов все исходные business rows сохранены; ожидаемо изменились только три служебных counter rows в employees_employeenumbersequence, projects_projectnumbersequence, work_tasks_tasknumbersequence от тестовых созданий. Эти изменения принадлежат тестовой подготовке, **не миграциям**. Ни source passwords, ни реальные profiles/tasks/projects не изменились. Новые test entities/Audit/Outbox — только в копии.

Фактический каталог объектов пуст; больших lookup проблем на нём не воспроизведено. Предел Employee UI lookup 200 и первая страница move UI остаются известными ограничениями, не доказанными проблемами текущего snapshot. Синтетические legacy строки тестов не объявляются реальными и не служат основанием mapping.

### Команды и воспроизведение

Все DB-changing команды ниже относятся **только к новой isolated copy**, не production. Paths/credentials заменяются настроенными безопасными значениями; env не печатать. Записывать новый source timestamp/SHA, не переиспользовать существующие имена DB/volumes.

```text
ssh -i <provided-identity> -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -p 40222 ivan@109.237.109.58 true
# Source inventory: stdin wrapper executes deployment/objects_inventory.py under installed /app Django runtime.
# PGOPTIONS: default_transaction_read_only=on, statement_timeout=60000, lock_timeout=5000, idle_in_transaction_session_timeout=60000.
# Source pg_dump command inside production db container, redirected to new protected local file:
pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB"
# Only in new isolated PostgreSQL:
pg_restore --exit-on-error --no-owner --no-acl -U objects_copy -d objects_copy
createdb -U objects_copy objects_original
pg_restore --exit-on-error --no-owner --no-acl -U objects_copy -d objects_original
# Exact checkpoint backend copied into inert isolated container using git archive + tar --strip-components=1:
git archive HEAD backend
```

Actual Python migration wrapper: MigrationExecutor → compare five plan entries with explicit allowlist → executor.migrate(targets) → call_command('migrate', interactive=False, verbosity=0) → table-fingerprint comparisons → check/migrate(check=True)/makemigrations(check=True,dry_run=True). Run only after baseline has been saved. Permissions/content types are created by post_migrate in the copy; DB ownership/ACL adaptation from --no-owner/--no-acl is environment preparation, not a production RBAC change.

Для повторения 32 API checks в isolated objects_copy: импортировать ObjectsTests, отсортировать его `test_` methods, для каждого создать instance, `with transaction.atomic(): case.setUp(); getattr(case,name)(); transaction.set_rollback(True)`. Использовать ALLOWED_HOSTS=testserver и guards по имени DB/container. Не запускать этот wrapper в source.

Browser command executed with private config (testDir points to worktree tests, outputDir outside Git, trace off, executablePath installed Edge, baseURL localhost:13031):

```text
AYS_OBJECTS_API_URL=http://localhost:18081
node frontend/node_modules/@playwright/test/cli.js test objects.spec.ts --config <private-playwright-config> --workers=1
```

Private artifacts/metadata находятся в защищённом каталоге вне Git. Raw data и dump в Git не включать. `backup.sh` с retention и restore scripts с DROP DATABASE не использовались. После проверок новые тестовые API/DB **остановлены**, volume/backup сохранены, local tunnel/UI закрыты. Production backend имеет прежние container ID/image и healthy status; исходный dump SHA повторно совпал. Копия не очищалась.

### Mapping, transfer и release

| Статус | Результат / основание |
|---|---|
| Code / synthetic acceptance | PASS; checkpoint runtime + окончательный browser-test diff проверен 6/6 |
| O0 актуальный snapshot | PASS для 09.10 source; все восемь целевых моделей пусты, grants и refs проверены с оговорённым scan coverage |
| Restored upgrade compatibility | PASS; five migrations, baseline preservation, checks, repeat plan и original restore |
| Legacy mapping | N/A — source Facility=0, Zone=0 |
| Репетиция переноса | N/A — переносить legacy нечего; backfill не выполнялся |
| Production release readiness | CONDITIONAL / NOT VERIFIED для полного выпуска; техническая DB совместимость PASS |
| Production deployment | NOT PERFORMED |

Нет неразрешённых реальных mapping/мультиюридических решений на этом snapshot. Это не blanket acceptance для будущих populated данных или другого источника. Перед выпуском остаются свежий maintenance DB/**media** backup, off-host checksum/restore, immutable release images и утверждённый actual migration plan; данный online DB snapshot не заменяет эти operational gates. Этот follow-up commit/push и обновление draft PR разрешены отдельным запросом на RC; новый production backup, merge и deployment в текущей задаче не выполняются.

## Release runbook — production release требует отдельного разрешения

Backup-only maintenance и full init **копии** выполнены выше. Production init, переключение release images и write-smoke ниже не выполнялись. При остановке старых workers использовать проверенный idle-loop helper ниже; shell PID1 не пересылает TERM sleep.

Runbook дополняет [PRODUCTION_DEPLOYMENT](PRODUCTION_DEPLOYMENT.md). Исполнение требует отдельного разрешения на maintenance/backup/smoke/deployment. Backup-only действия этой задачи записаны выше; production init, release переключение и write-smoke этого runbook не выполнялись. Выход каждого этапа — закрытый gate с evidence; отсутствие evidence означает STOP, а не допущение.

### 1. Зафиксировать входные данные и проверить drift после snapshot

До окна согласовать оператора, exact RC SHA, backend/frontend image digests, защищённый server env path, release source directory, maintenance window, off-host destination и recovery owner. RC SHA получить из дочернего commit выше и заморозить; нельзя использовать mutable branch/tag как идентичность release. Серверный nongit source в /opt/ays-connect не перезаписывать checkout целиком.

Снять read-only container IDs/images/health, safe source hashes, PostgreSQL version, applied migrations и source inventory установленным source-compatible runtime с READ ONLY/REPEATABLE READ и прежними timeouts. Сравнить с source baseline main `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`, image `182f57f5…`, 101 applied и cutoff выше. Ожидаемые production Location/Facility/Zone после snapshot не предполагаются: проверить заново все восемь counts, refs и реальные grants. Изменение их данных снимает применимость empty-legacy N/A к новой копии и требует новой inventory/mapping review/upgrade acceptance до выпуска. Новые обычные Work/Projects записи сами по себе допустимы: проверить сохранность свежего baseline вместо требования 1950 строк навсегда.

Неизвестный source/image/migration drift, новые unsupported scopes/неоднозначные legacy refs или неподтверждённый target — STOP. Тот же O0 PASS исторического dump не переименовывать в PASS свежего состояния. Сверить runtime/schema RC с проверенным кодом; при их изменении определить новые gates, а не использовать прежние 585/32/6.

### 2. Собрать immutable images и закрыть пользовательские writers

До maintenance собрать release images из exact clean RC source без .env/dump/media; frontend VITE_API_URL=/api/v1. Создать проверенный image override для init/backend/всех шести workers с одним backend digest и frontend_assets с отдельным frontend digest; inspect подтвердить SHA и наличие каждого image. Новая конфигурация должна сохранять production volumes, iiko protected env wiring и ограничения Gunicorn. Не менять фактические runtime secrets. `config --quiet` обязателен, полный rendered config не выводить.

Параметры ниже — обязательные согласованные абсолютные пути/ID, не места, угаданные runbook. Команды выполняются оператором на Linux только после разрешения:

```bash
# Set AYS_RELEASE_ENV, AYS_RELEASE_ROOT, AYS_IMAGES_OVERRIDE out of band.
dc() {
  docker compose --env-file "$AYS_RELEASE_ENV" -p ays-connect-production \
    -f "$AYS_RELEASE_ROOT/docker-compose.prod.yml" \
    -f "$AYS_RELEASE_ROOT/docker-compose.iiko.yml" \
    -f "$AYS_IMAGES_OVERRIDE" "$@"
}
dc config --quiet
dc ps
```

Доказать maintenance ingress allowlist: доступ только оператору/согласованным smoke personas, остальные клиенты не могут писать. Если такого механизма нет, proxy остаётся остановленным до его настройки; простое обещание «не открывать writes» не является защитой. Зафиксировать IDs прежних containers/images и конфигурацию для resume/rollback. Затем закрыть traffic и остановить foreground/background writers с timeout, соответствующим iiko graceful timeout 300s:

```bash
# Saved IDs are the containers captured before this release window.
# Pause the verified sleeping periodic backup before ingress closure.
docker pause <saved-backup-container-ID>
docker stop --time 330 <saved-proxy-container-ID> <saved-backend-container-ID>
# Execute the idle-loop helper below for each of the six saved workers.
# Do not interrupt Python jobs; verify every worker has exited.
dc ps
```

DB/Redis остаются running. Подтвердить завершение in-flight writes и отсутствие иных writers/cron/integration jobs. Пока это не доказано, backup/maintenance gate не закрыт. Записать начало write freeze UTC.

### Завершение idle worker loops перед backup

Для прежних shell -ec while loops проверить каждый сохранённый worker ID: если есть выполняющийся Python job, дождаться его завершения. Только единственный idle sleep можно прервать TERM: shell -e завершится, не начав следующую итерацию. Не отправлять TERM business Python jobs и не считать forced kill подтверждением безопасного завершения. После helper обязательно inspect Running=false и source client/in-flight/prepared=0; Docker exec exit 137 допустим только при доказанно завершённом контейнере без прерванного job.

```bash
docker exec -i <saved-worker-ID> python - <<'PY'
import os, pathlib, signal
processes = []
for entry in pathlib.Path('/proc').glob('[0-9]*/comm'):
    try:
        processes.append((int(entry.parent.name), entry.read_text().strip()))
    except FileNotFoundError:
        pass
assert not any(name.startswith('python') and pid != os.getpid() for pid, name in processes), 'Worker busy: wait, do not interrupt'
sleepers = [pid for pid, name in processes if name == 'sleep']
assert len(sleepers) == 1, 'Unexpected process layout: stop and review'
os.kill(sleepers[0], signal.SIGTERM)
PY
# Verify saved worker stopped; repeat for all six; then verify zero DB transactions.
```

Pause sleeping backup **перед** закрытием ingress. Resume old services по сохранённым IDs и `docker unpause <saved-backup-ID>` после verified off-host copy, без нового retention invocation. Если backup активно пишет, дождаться окончания до pause; не freeze его в середине архива.

### 3. Свежий согласованный DB/media backup без retention

Согласовать новый уникальный BACKUP_ID; существующее имя означает STOP. PG dump и media брать в одном закрытом write window, сохранить ownership/ACL metadata для восстановления. Secret конфигурацию хранить отдельно штатно, не архивировать .env в Git. Не использовать backup.sh с retention либо restore scripts с DROP DATABASE.

```bash
# BACKUP_ID is agreed and matches ^[A-Za-z0-9_-]+$; no slash or traversal.
dc run --rm --no-deps --entrypoint sh -e BACKUP_ID="$BACKUP_ID" backup -ec '
  umask 077
  case "$BACKUP_ID" in ""|*[!A-Za-z0-9_-]*) exit 2;; esac
  destination="/backups/$BACKUP_ID"
  mkdir "$destination"
  pg_dump --format=custom --file="$destination/database.dump"
  tar -C /source -czf "$destination/media.tar.gz" media
  cd "$destination"
  sha256sum database.dump media.tar.gz > SHA256SUMS
  sha256sum -c SHA256SUMS
'
```

`mkdir` без -p защищает от перезаписи. Выйти при любой ошибке; записать source/application/migration version, время начала/окончания capture, filenames/bytes/SHA без содержимого. Backup не считается выполненным по одному сообщению shell или наличию старого файла.

### 4. Защищённая off-host копия и restore именно из неё

В согласованный новый каталог на другой машине вне Git/общих sync shares передать **database.dump, media.tar.gz, SHA256SUMS** по SSH. Доступ — только оператор/recovery owner, на Windows явный ACL; проверить место, шифрование/политику хранения и защищённый транспорт. При необходимости export из named volume делать через docker cp из остановленного backup container в новый private staging directory, не открывая permissions каталога всему миру. Не выводить пароль/DSN/ключ. Сверить каждый SHA на source и off-host; несовпадение — STOP.

Restore gate запускается **из off-host файлов**, не из server-local архива. Новые project/network/PG volume/DB/media volume, internal=true, без public ports/production credentials/networks/media и без workers/init/cron. Проверить tar member paths до распаковки; только относительные media/ paths без traversal и опасных link targets. Dump original immutable. Restore owner/ACL adaptation и тестовый signing secret протоколировать отдельно от schema/data изменений.

В новой пустой БД выполнить pg_restore --exit-on-error, проверить исходные constraints, baseline counts/UUID/code/types/FK, media hashes и referenced file availability, RBAC fingerprints. В ещё одной новой базе повторить original-version restore. Нельзя очищать существующую rehearsal DB/volume.

На свежей isolated upgraded copy проверить полный **фактический init command** из RC Compose, включая migrate, seed_permissions, collectstatic и подготовку прав файлов, без dependency traversal и без production mounts. Предыдущий PASS проверял migrations/post_migrate, не утверждает, что весь production init/seed_permissions уже репетирован. seed_permissions может согласованно обновить catalog labels; RolePermission/EmployeeRole и source user privileges должны остаться прежними. Объяснить все catalog/data deltas, повторить affected acceptance на свежих данных. Off-host DB+media restore и полный init подтверждены для frozen snapshot выше. Их актуальность/повторение для нового release restore point проверять отдельно; PASS прежнего online snapshot не заменяет full-init evidence.

### 5. Проверить точный migration plan и применить один раз

На свежей копии ожидаются ровно пять additions:

```text
access_control.0003_alter_rolepermission_scope
organizations.0004_location_address_location_business_status_and_more
organizations.0005_objects_guards_and_permissions
organizations.0006_responsibility_service_guard
organizations.0007_binding_lifecycle_guards
```

Сохранить ordered plan/hash и после него повторный empty plan. Если source изменился и delta другой — STOP, новый plan review/upgrade, не «догонять» production предположениями. Check/drift/RBAC/business data preservation и archive constraints должны пройти в копии до production migrate. Нельзя переписывать уже применённые migration files.

После закрытия gates 1–4 и отдельного разрешения оператора, при writers still stopped:

```bash
dc run --rm --no-deps init
```

Это единственный production migration/init invocation. Проверить вывод против approved plan; не повторять init вслепую при partial failure. Отдельно проверить migrate --check, grants fingerprints, zero unexpected classification/backfill и отсутствие unknown migrations. При unexpected data/privilege delta — STOP с write freeze.

### 6. Обновить сервисы, провести авторизованный smoke, открыть writes

```bash
dc run --rm --no-deps frontend_assets
dc up -d --no-deps --no-build --force-recreate backend
```

Backend и assets должны разрешаться к заранее проверенным immutable images; workers пока paused, proxy закрыт или под доказанным maintenance allowlist. Проверить backend health/ready, exact SHA/image, migration status, logs, старые consumers и файл-доступ. Не запускать frontend_assets повторно через dependency traversal.

Разрешение smoke должно явно назвать test accounts с нужными правами, маркированный объект, тип/timezone, maintenance route и допустимые write effects. Не создавать роль/аккаунт и не менять реальный пароль без такого разрешения. Для существующего scoped пользователя без глобальных прав согласовать доступный LegalEntity context; при пустом справочнике использовать согласованную global test persona, не создавать реальные LE/OrgUnit по предположениям.

Авторизованный UI/API smoke:

1. Через согласованный test-only ingress открыть UI exact RC assets. Создать ровно один `RELEASE-SMOKE-<RC_SHA>-<UTC>` объект типа office в preparation, timezone Asia/Novosibirsk. Сохранить payload/Idempotency-Key в закрытом журнале; повторить API с тем же ключом/телом — тот же UUID, второе создание/Audit/Outbox отсутствует. Другой payload с тем же ключом — 409.
2. Создать одну маркированную зону с текущей version; проверить parent UUID, наследованный контекст и рост version. Проверить list/detail/tree/lookups/counts и отсутствие лишних созданий. Без действующих согласованных LE/ответственного не переводить объект в operating.
3. Проверить view/manage/create и denied persona: недоступный объект detail 404, запрещённая операция 403, scoped counts/list/lookup не раскрывают hidden IDs. location.manage не подразумевает view, ответственному права автоматически не выдаются. Старый Location API write 405; Admin read-only. Проверить связанные People/Work/Requests/Projects без создания реальных задач/обращений вне разрешённого smoke.
4. Audit/Outbox entries относятся только к разрешённым действиям, повтор idempotency не дублирует событие. Workers ещё paused: никакой неразрешённой внешней доставки. Зарегистрировать разрешённые synthetic records; не удалять их прямым SQL. При согласованной уборке использовать domain close/archive после снятия blockers, сохраняя историю.

Проверка через SSH-only backend tunnel допустима до запуска proxy; локальные endpoints только loopback. Затем разрешённый maintenance ingress открывает proxy исключительно для smoke/оператора:

```bash
dc up -d --no-deps --no-build --force-recreate proxy
```

Проверить внешний HTTPS/certificate, live/ready, SPA load и authenticated read-only routes при закрытом доступе остальных пользователей. После успешного smoke запустить workers из того же backend digest:

```bash
dc up -d --no-deps --no-build --force-recreate recurrence_worker schedule_worker \
  sla_worker escalation_worker notification_worker performance_worker
```

С этого момента могут появиться **новые реальные background writes/доставки**, даже без публичного traffic. Зафиксировать время, проверить health/heartbeats, Outbox/failed/repeated events, real integration behavior и data invariants. Только после всех checks снять maintenance ingress restrictions, записать UTC открытия user writes. Возобновление periodic backup/retention — отдельное согласованное действие с сохранением pre-release restore point; не запускать retention автоматически сразу после release.

### 7. STOP и rollback с учётом новых записей

STOP: неизвестный production drift/новые legacy ambiguity, невалидный backup/checksum/media restore, unexpected plan, grant widening или business-data change, unhealthy service, scope leak/duplicate/cycle/archive bypass, неверный SHA/image/assets, failed/repeated Outbox, непредусмотренная внешняя отправка либо отсутствие доказанного write freeze/maintenance restriction. Оставить public ingress закрытым, остановить release writers, сохранить logs/evidence/current data.

- До любых migrations и переключения: возобновить именно прежние containers через docker start сохранённых IDs; не docker compose start с зависимостями. Backup failure не требует restore или seed. Проверить исходные image/migration/RBAC fingerprints и health, затем отдельно открыть traffic.
- После migrations, но **до новых реальных writes**, code-only rollback допустим лишь при проверенном schema compatibility window. По умолчанию считать его непроверенным. Восстановить fresh pre-release DB/media backup в **новые** DB/volumes, сравнить hashes/constraints/RBAC/прежние source values, согласованно переключить прежние images/config; изменённую DB/volumes сохранить для расследования. Не выполнять automatic reverse migrations, DROP либо перезапись действующей DB.
- Если единственные post-backup writes — заранее разрешённые synthetic smoke records/operational heartbeat/catalog changes, recovery owner должен явно разрешить их потерю после сохранения evidence; нельзя назвать такую БД «неизменённой». Учитывать Audit/Outbox и любые already delivered effects, которые restore не отменяет.
- После запуска workers/доставок или открытия пользовательских writes презумпция **новых реальных данных**: запрет blind restore старого backup. Закрыть ingress/остановить writers, сделать отдельную защищённую аварийную копию текущей DB/media по разрешению, определить полный delta и сохранение/replay новых данных либо forward fix. Переключение/restore только после решения recovery owner о сохранности данных и согласованной компенсации необратимых внешних действий.

### Остаточные условия выпуска после репетиции

См. конкретный план и точный список выше. Snapshot backup/off-host restore/full actual init PASS; актуальность rollback point после возобновлённых writes должна проверяться в новом release window. Production smoke, immutable frontend/production config и отдельное release разрешение остаются обязательными. **Production readiness CONDITIONAL; deployment NOT PERFORMED.**
