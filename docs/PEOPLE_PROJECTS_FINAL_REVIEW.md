# People + Projects — финальное ревью локального checkpoint

Дата: 27.09.2026. Checkout: `C:\Users\riddl\OneDrive\Документы\AYS Connect актуальный`; branch `codex/projects`; база diff и текущий HEAD `f13bfce249b0c22311621c577e4337887018f9c3`. Ревью включает tracked diff и все untracked файлы. Другой checkout `AYS Connect` не изменялся.

## Замечания и исправления

| Критичность | Замечание | Исправление | Evidence |
|---|---|---|---|
| Высокая | Work reopen/reject notification могла остаться видимой или уйти в Email после утраты получателем доступа к закрытой задаче. | Текущий `TaskSelector.visible_to()` проверяется при materialization, delivery и SQL-фильтрации In-App; доставка подавляется с `TASK_ACCESS_REVOKED`. Live harness использует настоящую scoped Work-задачу. | Затронутый набор 65/65; People worker 5/5 причин; полный backend 444/444. |
| Средняя | Создание этапа/контрольной точки не проверяло People lifecycle ответственного; неверный диапазон дат этапа мог завершиться DB error вместо бизнес-ответа. | Проверки перенесены в доменный сервис до записи; regression подтверждает неизменность Project version, Audit и Outbox при отказе. | Projects 29/29; полный backend 444/444. |
| Средняя | Часть Projects write endpoints молча игнорировала неизвестные поля, хотя acceptance заявлял строгий контракт. | Общий `StrictSerializer`; lifecycle и comments regression подтверждают 400 и отсутствие мутации. | Projects 29/29; API 37/37. |
| Низкая | Старый live People worker использовал несуществующий UUID Work-задачи и перестал бы быть воспроизводимым после scope fix. | Harness создаёт синтетическую Work-задачу и scoped роль, credentials остаются в private staging volume. | Live People worker PASS. |

Открытых дефектов высокой/средней критичности в принятом People и Projects scope после исправлений не найдено. Канонического Work dependency engine нет; это задокументированное продолжение, а не blocker первого релиза. Forgotten-password остаётся отдельным People product gap.

## Финальный gate

- PostgreSQL 17.11 backend: **444/444 PASS**, skipped 0, 107.033s.
- Projects domain/security/concurrency: **29/29 PASS**; затронутые People+Notification+Projects: **65/65 PASS**.
- Projects staging API: **37/37 PASS**; unauthorized scope, idempotent create и Work acceptance PASS.
- Playwright Projects: **2/2 PASS**, включая manager/executor separation, link существующей Work-задачи и board transition через Work command.
- Projects due worker: один due notice/outbox/notification, In-App+Email, повторный scan 0.
- People worker: пять причин, по одному logical notification, In-App+Email и пять синтетических Mailpit сообщений.
- TypeScript и Vite production build PASS; Django check, migration drift и `migrate --check` PASS.
- Clean Projects migration, People→Projects upgrade и synthetic backup/restore относятся к неизменившейся миграционной схеме `projects0001..0008`; после ревью миграции не менялись.
- `git diff --check` и known synthetic secrets/JWT scan по Audit/Outbox/staging logs PASS.

## Состав checkpoint

Рекомендуется один интегрированный checkpoint: People Acceptance и Projects first release вместе с общими изменениями Work, RBAC, auth revocation и Notification Core; append-only migrations; frontend; staging compose/harness; acceptance/API/user документация и воспроизводимые тесты. Разделение сейчас потребовало бы искусственно делить общие файлы `work_tasks`, `notifications`, `access_control` и итоговую документацию и создало бы промежуточное состояние, не соответствующее проверенному gate.

В checkpoint не входят игнорируемые `.env`, `.env.pilot`, `.pilot-credentials.local.txt`, `backend/db.sqlite3`, `backend/media/`, `frontend/dist/`, `frontend/test-results/`, Docker volumes, dumps и staging private credentials. Commit/push/merge/deployment не выполнялись.
