# Импорт ЦФО в рабочую базу

13.10.2026. После согласования пакета пользователь указал создавать все UUID
новыми и поручил «Приступай». Подтверждён timezone офиса Asia/Novosibirsk;
остальные выбраны по согласованным региону/городу. Импорт выполнен в production
данными, без deployment PR 3, смены images, миграций, frontend или workers.

Созданы **21 LegalEntity, 5 OrgUnit и 50 Location** — 76 новых UUID v4.
Сохранены 54 связи с юрлицами; у одной службы intentional null.
Пять исключений не создавались и не удаляют старые записи. Новые objects
имеют business_status=preparation. Существующие 5 Location и 4 Work Task
сохранены с прежними IDs/полями; похожий существующий объект не заменялся.
Руководители сохранены как план назначения, не Employee/Position/Responsibility.
Новые сотрудники, аккаунты, права, targets и назначения — 0.

## Проверка до записи

Protected online DB/media snapshot: **2026-10-13 11:36:53.695039 UTC**.
EFS off-host и отдельный LUKS restore контур с internal network, no egress,
no workers, no production mounts/ports. Source image совпадает с production.
Restore **201/201 tables** по fingerprint — PASS.
Импорт выполняется штатными ObjectService/OrgUnitService; LegalEntity получает
явный Audit/Outbox hook в той же общей transaction. Существующий active owner
actor проходит проверку и Object domain policies; grants не выдаются.

| Проверка | Результат |
|---|---|
| Ошибка после первой записи / rollback всех таблиц | PASS |
| Первое создание | 21 LE + 5 OrgUnit + 50 Location |
| Повтор в копии | 0 новых entities / Audit / Outbox, те же UUID |
| Исходные Users/Employees/roles/permissions/grants/targets/Tasks | fingerprint PASS |
| Старые Location | все поля/UUID сохранены |
| Existing pending location.* | сохранены |
| Production Audit/Outbox delta | 76 / 76 |
| UUID v4 / FK integrity | PASS |
| Owner internal API | 76/76 PASS |
| Existing scoped employee: deny new objects | 50/50 PASS, grants не расширялись |
| Public HTTPS/live/ready | 6/6 HTTP 200 |
| Workbook saved UUID/FK, package SHA/CRC/EFS | PASS |

## Evidence и применение

`I:\AYS Connect\TaskPatch\CFO-import-20261013` содержит executed input,
runner SHA, production ledger, API/scope/health proof, workbook со всеми UUID,
manifest и protected snapshot/rehearsal. Raw dump/media/private inspect/logs
в Git и раздаваемый пакет не включены. Executed input сохранён неизменным как
authorized-plan.json; итоговый import-plan.json содержит actual UUID/status applied.
Правила нового UUID не означают повторное создание при replay своего импорта:
LE/OrgUnit codes + ownership markers и actor-bound Object idempotency сохраняют
уже созданные IDs. Partial/unknown outcome требует reconcile, не blind retry.

Это добавление данных, не замена legacy или выпуск патча. Дальнейшее назначение
руководителей требует активных Employees и manager positions/членства в OrgUnit.
УК намеренно без руководителя; старые задачи не перепривязывались. До выпуска
PR 3 остаются его самостоятельные code/design/bot/release gates; импорт не
даёт нового разрешения merge/deployment. Online snapshot не является frozen
точкой переключения; после новых writes нельзя blind restore без сохранения tail.
