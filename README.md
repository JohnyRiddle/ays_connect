# AYS Connect

Интеграция iikoCard опубликована на [ays-connect.ru/iiko-cards](https://ays-connect.ru/iiko-cards).
Создание, проверка, переоформление, комментарии и пополнение описаны в
[итоговом отчёте](docs/IIKO_PROJECT_REPORT.md); серверный контур и откат — в
[инструкции развёртывания](docs/IIKO_DEPLOYMENT.md). Эта локальная ветка является
checkpoint более ранней базы; перед объединением с актуальной main нужна интеграция.

Корпоративная платформа управления сотрудниками и операционными процессами. Реализованы ядро, задачник, чек-листы/ХАССП, датчики, инциденты, аналитика, уведомления и backend первого этапа корпоративной базы знаний.

## Быстрый запуск

1. Выполните (для локальной демонстрации `.env` не обязателен):

```bash
docker compose up --build
```

2. Откройте [http://localhost:3000](http://localhost:3000).

Для любого внешнего окружения скопируйте `.env.example` в `.env` и обязательно замените ключ и пароли.
Если стандартные порты заняты, задайте `BACKEND_PORT` и `FRONTEND_PORT` в `.env`.

Демо-вход: `ivan@demo.ays-connect.local` / `Demo12345!`. Данные вымышлены и создаются командой `python manage.py seed_demo`.

## Сервисы

- frontend: `http://localhost:3000`;
- API: `http://localhost:8000/api/v1/`;
- Django admin: `http://localhost:8000/admin/`;
- health check: `http://localhost:8000/api/v1/health/`.
- Swagger UI: `http://localhost:8000/api/docs/`;
- база знаний API: `http://localhost:8000/api/v1/knowledge/`.

## Локальная разработка без Docker

Backend требует Python 3.12, frontend — Node.js 20. Для локальной SQLite-базы можно не задавать `DATABASE_URL`.

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_demo
.venv/Scripts/python manage.py runserver
```

```bash
cd frontend
npm install
npm run dev
```

## Тесты

```bash
cd backend
python manage.py test
```

Архитектура и этапы описаны в `PROJECT_PLAN.md`, принятые решения — в `DECISIONS.md`. Описание базы знаний находится в `docs/KNOWLEDGE_BASE.md`. Максимальный размер файла задаётся переменной `KNOWLEDGE_MAX_FILE_SIZE_MB` (по умолчанию 50 МБ).

## Восстановление контекста

Перед продолжением разработки на другом компьютере прочитайте:

- `AGENTS.md` — практические правила работы;
- `docs/CURRENT_STATE.md` — актуальная точка передачи;
- `docs/PROJECT.md` — назначение и ближайшие цели;
- `docs/ARCHITECTURE.md` — фактическая архитектура;
- `docs/DECISIONS.md` и корневой `DECISIONS.md` — подтверждённые решения.

Production internal API доступен под `/api/internal/v1/`; канонические задачи реализованы в `backend/work_tasks`, а каталог услуг — в `backend/service_requests`.
