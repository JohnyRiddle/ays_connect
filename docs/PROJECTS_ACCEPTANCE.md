# Projects — локальная приёмка, 15.09.2026

## Финальное ревью checkpoint — 27.09.2026

Полный diff от `f13bfce` повторно проверен вместе с новыми файлами. Исправлены две найденные проблемы: создание этапа/контрольной точки теперь отклоняет недоступного по People lifecycle ответственного, а неверные даты этапа возвращают контролируемую бизнес-ошибку с полным rollback; Work-уведомления reopen/reject теперь проверяют текущий SQL scope задачи при materialization, delivery и чтении In-App. Все write serializers Projects отклоняют неизвестные поля.

Финальный PostgreSQL gate после исправлений: Projects **29/29**, затронутые People/Notification/Projects **65/65**, полный backend **444/444** за 107.033s. Повторно прошли Projects API **37/37**, browser **2/2**, Projects worker, People worker по пяти причинам, TypeScript/Vite build, Django check, migration drift и sensitive evidence scan. Миграции после исходного clean-upgrade/restore evidence не менялись. Полный review и состав checkpoint: [PEOPLE_PROJECTS_FINAL_REVIEW.md](PEOPLE_PROJECTS_FINAL_REVIEW.md).

База: `C:\Users\riddl\OneDrive\Документы\AYS Connect актуальный`, ветка `codex/projects`, HEAD `f13bfce249b0c22311621c577e4337887018f9c3` плюс сохранённые незакоммиченные People-изменения и новые Projects-изменения. Все данные и аккаунты проверки синтетические, контур `docker-compose.projects-staging.yml`; production не затрагивался. People Acceptance закрыт отдельно на той же базе до создания ветки: [PEOPLE_STAGING_ACCEPTANCE.md](PEOPLE_STAGING_ACCEPTANCE.md).

| Требование | Проверка / evidence | Результат | Оставшийся blocker |
|---|---|---|---|
| Project, PRJ номер, lifecycle, роли, этапы, точки, TaskLink | PostgreSQL `projects.tests`: 29/29 в финальном full backend 444/444; сервисные/API/SQL/concurrency проверки | PASS | Нет |
| One Work Task, приёмка и completion | Проектные тесты и staging API: `REVIEW` блокирует завершение; создание/link/move/rollback; Work reopen реактивирует Project | Реализовано | Нет |
| SQL scope, доступ к Work, Audit/Outbox | Проектные тесты, synthetic outsider API, PostgreSQL rollback, защищённые attachments и Notification Core | Реализовано | Нет |
| UI: список, детали, доска, timeline, создание/привязка задач, обсуждения, документы | Синтетический Playwright manager/executor/outsider 2/2, включая перенос карточки `draft→open` через Work publish; TypeScript/Vite build | PASS | Нет для включённых сценариев |
| Уведомления и повторная доставка | Живой worker, Mailpit, InApp/Email, повторный due scan | Один due intent; повтор без дубля | Нет |
| Миграции и восстановление | Clean PG17.11 migrate через `projects0008`; People→Projects upgrade; synthetic pg_dump/restore 193 tables/140 rows и DB guards; финальный `migrate --check` и drift | PASS, схема после API правки не менялась | Нет |
| Зависимости задач и метрика блокирующих задач | Аудит Work: канонического dependency engine нет | Отложено по ТЗ | Отдельное product-решение о движке зависимостей |
| Final Quality Gate на окончательном коде | PostgreSQL backend 444/444 (107.033s), Projects API 37/37, браузер 2/2, worker due/outbox/notification=1 и повторный scan=0, People worker 5/5 причин, frontend build, check0/drift0/migrate check, `git diff --check`, Audit/Outbox/staging-log sensitive scan | **PASS** | Нет в первом релизе |

Финальный gate выполнен после последней API/UI правки на коде этой ветки. Ранние результаты 08.09.2026 не использованы как финальная проверка. Forgotten-password — отдельный product gap вне People и Projects приёмки. Commit/push/deployment не выполнялись.

При немедленном повторе браузерного harness синтетические login попытки достигли штатного staging throttle (`429`, `5/min`); это не принято как evidence. После истечения окна повторный безопасный browser reporter завершился **2/2 PASS** без HTTP failures. Лимиты приложения и реальные аккаунты не менялись.
