# Work Task actions UX — staging acceptance

**Дата:** 02.10.2026
**Ветка:** `codex/work-task-actions`
**База:** `origin/main` / `9855dac3881d3a79ec1a5d0cbe221ef7743f638c`

## Реализация

Карточка Work Task показывает один основной следующий переход согласно фактической state machine: `draft → publish`, `open → start`, `waiting → resume`, `in_progress → complete`, `review → accept`. Второстепенные разрешённые операции находятся в меню «Действия»; отмена отделена и расположена последней. Основное действие не дублируется.

Доступ формируется `TaskUXService` через существующие Permission и SQL scope. Для выполнения, временно заблокированного обязательным чек-листом, detail API возвращает `action_blockers.complete`; действие без полномочий не раскрывается. Наблюдение переключается существующими POST/DELETE `watch` endpoints.

«Выполнить» открывает completion dialog, сохраняет введённый результат при ошибке API и заранее сообщает о передаче на обязательную приёмку. Backend сохраняет прежнюю семантику: при `acceptance_policy != none` результат переходит в `review`; optimistic locking, Audit/Outbox и уведомления не менялись. Конфликт версии не повторяет команду автоматически и предлагает обновить данные.

## Проверки

| Требование | Проверка | Результат |
|---|---|---|
| State machine, выполнение, приёмка/отклонение, reopen/cancel | `work_tasks.tests.TaskLifecycleTests` | PASS |
| Stale version и Audit/Outbox rollback | `TaskDeadlineHierarchyConcurrencyTests` и существующие domain tests | PASS |
| Permission/scope и ограниченный пользователь | `TaskApiSecurityTests` + browser outsider | PASS |
| Обязательный checklist и понятный blocker | `SavedViewsAndUXTests.test_completion_blocker...` | PASS |
| Автор → исполнитель → принимающий | synthetic PostgreSQL staging browser | PASS |
| Draft / In progress / Review, меню, отсутствие дубля primary | `work-actions-ux.spec.ts` | PASS |
| Completion result, mandatory acceptance notice, API 500 input retention | `work-actions-ux.spec.ts` | PASS |
| Enter, Space, Escape и возврат focus | `work-actions-ux.spec.ts` | PASS |
| Frontend production build | `pnpm run build` | PASS, 1913 modules |
| Django check / migration drift / diff | `manage.py check`, `makemigrations --check --dry-run`, `git diff --check` | PASS |

Связанная с проектом задача и полный Projects lifecycle продолжают проверяться `projects-acceptance.spec.ts`; локаторы обновлены под подписи «Начать работу», «Выполнить» и completion dialog. Доменная проверка покрывает самостоятельные задачи, checklist, отмену/reopen, stale version и транзакционный rollback.

## Browser evidence

- Черновик: `C:\AYS-Backups\work-actions-20261002\work-actions-draft.png`
- Раскрытое меню: `C:\AYS-Backups\work-actions-20261002\work-actions-draft-menu.png`
- В работе: `C:\AYS-Backups\work-actions-20261002\work-actions-in-progress.png`
- На приёмке: `C:\AYS-Backups\work-actions-20261002\work-actions-review.png`
- Playwright artifacts: `C:\AYS-Backups\work-actions-20261002\work-actions-browser`

Контур использует только синтетических manager, executor и outsider; superuser для browser-сценария не использовался. Проверки выполнялись в изолированном synthetic staging; реальные задачи не затрагивались.

Релизный checkpoint разрешён после завершения этого gate.
