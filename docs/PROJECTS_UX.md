# Projects UX — staging review

**Дата:** 02.10.2026
**Ветка:** `codex/projects-ux`
**База:** `origin/main` / `d2f91d03b5b307d08d777812bcaae7653346eedd`

## Результат

Страница проекта перекомпонована вокруг основного сценария «увидеть задачи → создать
или открыть задачу». Шапка стала компактной, параметры перенесены в панель настроек,
редкие lifecycle-действия и история — в дополнительное меню. По умолчанию открываются
задачи; вкладки и представление задач сохраняются в URL и поддерживают reload и
браузерные переходы.

Задачи сгруппированы по этапам и показывают название, статус, ответственного и срок.
Фильтры выполняются сервером до пагинации, totals рассчитаны по всей доступной SQL-scope
выборке, а поиск, статус, ответственный, страница, вкладка и представление сохраняются в
URL. Создание, привязка и создание из шаблона открываются в отдельных панелях. Создание из
строки этапа подставляет этап. Список, доска с разрешёнными Work-переходами и «Сроки»
используют существующую сущность Work Task и текущие API. Обзор, команда, защищённые
файлы, обсуждение и история загружаются по запросу.

Боковое меню собрано в сворачиваемые группы с состоянием для конкретного пользователя.
«Мой профиль», редактирование и штатный logout перенесены в доступное меню аккаунта.
`/people/me` стал read-only, self-service сохранён на `/people/me/edit`; backend permissions,
optimistic locking, change requests, Audit/Outbox и Notification Core не ослаблялись.

## Проверки окончательного кода

| Требование | Проверка | Результат |
|---|---|---|
| TypeScript и production bundle | `npm run build` в staging frontend image | PASS, 1812 modules |
| Projects domain, server filters и template integration | Projects 30 + TaskTemplateTests 4 на PostgreSQL 17.11 | PASS, 34/34 |
| Create/link/Work lifecycle/acceptance/scope | `playwright.projects.config.ts` | PASS, 2/2 |
| URL filters/tab/view/page, reload, Назад, список/доска/сроки | `playwright.projects-ux.config.ts` | PASS |
| Account menu, read-only/edit routes, API error retention, logout, desktop/mobile/keyboard | `account-navigation.spec.ts` | PASS |
| Создание из этапа и сохранение ввода при API 500 | synthetic browser intercept | PASS |
| Из шаблона: UI, этап, параметры и приёмка | synthetic template + повтор того же idempotency request | PASS, одна Work Task |
| Settings, team, files, discussion, history | lazy-tab/panel browser checks | PASS |
| Desktop/mobile, отсутствие внешних fonts и page errors | screenshots + browser assertions | PASS |
| Diff integrity | `git diff --check` | PASS |

Browser evidence отдельно подтверждает положительный сценарий «Из шаблона». Idempotent
staging seed создаёт активный синтетический шаблон, принадлежащий synthetic manager;
роль получает только `task_template.view` и `task_template.use` со scope `own`.
Superuser и обход проверки доступа не используются. Через UI шаблон создаёт задачу
«Проверить готовность сезонного меню» в этапе «Запуск». Проверены `source_template`,
priority `high`, completion policy `manual`, acceptance policy `author`, связь с проектом
и этапом. Повторная доставка точного UI-запроса с тем же `Idempotency-Key` получила 200,
а выборка проекта сохранила ровно одну Work Task из этого шаблона.

Отдельно domain-test `test_create_inside_project_and_template_keep_one_work_task`
проверяет транзакционную реализацию ProjectTaskService. Он не используется как замена
browser evidence.

## Evidence

- desktop: `C:\AYS-Backups\projects-ux-20261002\projects-ux-desktop.png`;
- mobile: `C:\AYS-Backups\projects-ux-20261002\projects-ux-mobile.png`;
- sidebar expanded/collapsed: `C:\AYS-Backups\projects-ux-20261002\sidebar-expanded.png` и
  `C:\AYS-Backups\projects-ux-20261002\sidebar-collapsed.png`;
- Playwright artifacts: `C:\AYS-Backups\projects-ux-20261002\projects-browser` и
  `C:\AYS-Backups\projects-ux-20261002\projects-ux-browser`.

Preview доступен локально по `http://127.0.0.1:18081`; использованы только синтетические
данные. Production и реальные аккаунты не затрагивались.

## Ограничения

- движок зависимостей задач, бюджеты и новый планировщик не входят в этот этап;
- milestone editing остаётся на существующем API и требует отдельного компактного UX,
  если это будет включено в следующий продуктовый этап.

Commit, push и deployment не выполнялись.
