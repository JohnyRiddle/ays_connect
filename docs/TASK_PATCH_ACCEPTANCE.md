# Патч задач / Telegram API — результаты приёмки

13.10.2026. Изолированный workspace `codex/task-telegram-patch`.
Base `origin/main` 62c61ed; базовый runtime идентичен checkpoint 713be6b; код патча 98dfafa.
Незакоммиченный опубликованный дизайн и исходные dirty-файлы других worktrees
не включались и не редактировались. Commit/push и черновой PR разрешены пользователем 13.10.2026. Merge/deployment не выполнялись.

| Gate | Результат | Границы |
|---|---|---|
| Полный backend на PostgreSQL 17 | PASS, **672/672**, 3 изолированные test DB clones | фиктивные данные, не production snapshot |
| Новые сценарии патча | PASS, **38** внутри полного набора | включая reservation/binding races и upgrade |
| Django check | PASS | конфигурация изолированного контура |
| makemigrations --check --dry-run | PASS, No changes detected | только пять добавочных migrations |
| TypeScript/Vite build, npm ci | PASS | локальный immutable bundle; Docker daemon недоступен |
| Browser desktop 1280 / mobile 390 | PASS, **6/6** | Chromium, реальный изолированный Django API и PostgreSQL |
| OpenAPI export | PASS, **8 реализованных paths** | profile JWT и 5 service-only методов, не предлагаемые URL |
| git diff --check | PASS | без исходных сторонних dirty-файлов |
| Реальная доставка через @AYS_ai_expert_bot | **PASS, 2 сообщения**, получатель подтвердил | API copy harness + real transport; постоянный HTTPS adapter NOT VERIFIED |
| Fresh production-copy / protected frozen rollback point | **PASS**, 201 таблица / restore DB+media+frontend | 38/38 focused; полный серверный повтор resource-limited; [evidence и blockers](TASK_PATCH_REHEARSAL.md) |

## Проверенные случаи

Подразделение и единственный активный руководитель по manager_position;
неактивное подразделение не показывается; руководитель с другой должностью/из
другого подразделения и неоднозначная настройка отвергаются. Ответственный
остаётся после назначения исполнителя. Исполнитель может отсутствовать.
Фильтры выбора учитывают активность, подразделение, User и объект. Primary location
или членство не заменяют grants. Новые задачи проекта используют объект проекта
и отвергают руководителя без доступа; scope проверен на canonical ObjectService object.

Все пять приоритетов, критическая 3 часа, high 24, normal 72, low 168; blocking
с явным сроком. Пересчёт от исходного created_at, просрочка, история и обязательная
причина manual deadline. Project active_priority=null, наследование и конфликт
с индивидуальным сроком; старый null due_at тоже работает в API, filters, counters
и overdue worker. Повтор overdue не создаёт второй notice на тот же дедлайн.
Публикация/передача/возврат в работу старой задачи требуют явного department setup.

Наблюдатели добавляются/снимаются с историей; PARTICIPATING не даёт через watching
закрытие, reassign или deadline. Несколько ролей объединяются. Mention без доступа
не открывает Task и не создаёт content delivery. Inactive/suspended mention
отвергается; internal comment не доставляется без права. UI выбирает нескольких
наблюдателей, ищет mentions и отправляет Employee UUID, не только текст.

Код привязки хранится как hash, истечение/одноразовость/conflict/relink/unlink;
private chat обязателен. Одновременное погашение имеет одного победителя. Два
claim не получают одну delivery. До begin резерв можно перевыдать, после begin
истечение/ambiguous дают unknown. ACK с тем же message ID повторяется безопасно;
другой ID отвергается. Retry/backoff, blocked status, revoke binding/access,
inactive recipient, internal access и ротация/отзыв service credentials.
Bot credential отвергнут обычными employee/tasks/attachments/roles API.
Pull worker не забирает новые task deliveries в direct sender.

Request POST закрыт даже для superuser; прямой /requests/new предлагает Task.
Исторические requests/comments/attachments API не удалены. Backend regression
проверяет прежние Request/People/Objects/Projects/Work политики.

Synthetic migration proof откатывает только пустой тестовый schema к work_tasks
0004 / notifications 0005, создаёт старую Task/history/assignment/grant и pending
location event, затем применяет additions. UUID/number/targets/priority/version/
history/RolePermission/EmployeeRole/event ID сохраняются, department остаётся null,
grants active, location pending, никаких автоматических notices или руководителей.
Это не доказывает совместимость заполненной рабочей БД или реальных media.

## Воспроизведение и evidence

```text
backend: python manage.py test --parallel 3 --noinput
backend: python manage.py check
backend: python manage.py makemigrations --check --dry-run
backend: python manage.py export_bot_contract --output ../docs/telegram-bot/openapi.json
frontend: npm ci && npm run build
frontend: playwright test --config playwright.task-patch.config.ts
```

Backend требует отдельного PostgreSQL, не старый Docker volume. Browser config
фиксирует localhost:3017/8017 и требует `AYS_TASK_PATCH_FIXTURE` с UUID **фиктивной**
базы task_patch_ui. Артефакты `AYS_TASK_PATCH_OUTPUT` держать вне Git; примеры
тестового пароля относятся только к synthetic .invalid аккаунту. Live smoke
через этот config на production не выполнять.

Raw локальные logs: `C:/Users/riddl/.codex/tmp/task-patch-pass-all.log` и финальный
gate log (указан в manifest); browser screenshots/traces — отдельный temp-каталог.
В repository/handoff входит summary и OpenAPI, а не сессии, DB или credentials.
Финальный handoff manifest фиксирует только SHA256 передаваемых файлов.

Release readiness — **CONDITIONAL**. Обязательные непроверенные gates, интеграция
с опубликованным дизайном, административный preflight, startup/recovery и
ограничения: [TASK_PATCH_RELEASE.md](TASK_PATCH_RELEASE.md).

## Уточнение 13.10.2026: карточка объекта
Убраны вкладка сервисных заявок и кнопка их создания из карточки объекта. Старый параметр tab=requests переключается на зоны; исторический API и данные сохранены. Production ещё использует версию до PR #3.
