# AYS Connect — инструкции для Codex

AYS Connect — корпоративная платформа сотрудников и операционных процессов. Архитектура: модульный монолит Django/DRF, React/TypeScript SPA, PostgreSQL и Redis.

## Перед работой

Прочитать `README.md`, `docs/CURRENT_STATE.md`, `docs/PROJECT.md` и релевантную фазовую документацию. Проверить ветку, Git-статус и remote. Не перезаписывать незакоммиченные изменения.

## Структура

- `backend/` — Django API и предметные приложения;
- `frontend/` — React/Vite SPA;
- `docs/` — актуальный контекст и документация production-фаз;
- `docker-compose.yml` — локальный запуск;
- `docker-compose.prod.yml` — серверный контур.

Production-задачи находятся в `backend/work_tasks`, каталог услуг — в `backend/service_requests`. Не смешивать их с legacy-приложением `backend/tasks` и не выполнять разрушительные миграции без отдельного плана данных.

## Команды

- Запуск: `docker compose up --build`.
- Backend-проверка: `cd backend && python manage.py check`.
- Миграции: `cd backend && python manage.py makemigrations --check --dry-run`.
- Тесты: `cd backend && python manage.py test`.
- PostgreSQL gate: `docker compose run --rm backend python manage.py test`.
- Frontend: `cd frontend && npm install && npm run build`.

## Правила завершения

Сохранять границы доменов, использовать существующие Permission/Audit/Outbox и production Organization/People сущности. Не добавлять `.env`, базы, media, ключи или токены. После существенных изменений обновить `docs/CURRENT_STATE.md` и профильную документацию. В отчёте указать проверки, Git-статус и предложить commit; commit/push выполнять только по явному запросу.
