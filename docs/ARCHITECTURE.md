# Архитектура AYS Connect

## Общая схема

```text
Browser → React/TypeScript (Vite) → Django REST Framework → PostgreSQL
                                      ├→ Redis
                                      ├→ AuditEvent
                                      └→ transactional OutboxEvent
```

Проект является модульным монолитом: один Django backend развёртывается целиком, а предметные границы представлены отдельными приложениями.

## Компоненты и точки входа

- `frontend/src/main.tsx` — текущая SPA и пользовательская навигация;
- `backend/config/urls.py` — корневые API-маршруты;
- `/api/v1/` — MVP/пользовательские API;
- `/api/internal/v1/` — production internal API;
- `backend/access_control` — permissions, roles и scope;
- `backend/employees`, `backend/organizations` — People/Organization Core;
- `backend/work_tasks` — канонический production Tasks Domain;
- `backend/service_requests` — каталог услуг, RequestType и schema snapshots;
- `backend/audit`, `backend/events` — аудит и Outbox;
- остальные Django-приложения — действующие MVP-домены знаний, обучения, датчиков, инцидентов и аналитики.

## Данные и интеграции

PostgreSQL является production-хранилищем; SQLite допускается только для лёгкой локальной разработки. Redis запущен как инфраструктурная зависимость и резерв для фоновой обработки. Файлы хранятся в Django media volume. Внешних обязательных SaaS-интеграций для локального запуска нет; Telegram представлен mock-командой.

Значимые доменные изменения выполняются сервисами в транзакции, фиксируются через `AuditService` и при необходимости публикуются в transactional Outbox через `DomainEventService`.

## Взаимодействие доменов

Production-домены переиспользуют `Employee`, `LegalEntity`, `OrgUnit`, `Location`, `FunctionalGroup`, `AssignmentTarget` и общую модель permissions. Service Catalog пока только описывает будущие заявки; создание Request и связь Request → Task относятся к Phase 1.2B.

## Локальный запуск

1. При необходимости скопировать `.env.example` в `.env` и заменить значения.
2. Выполнить `docker compose up --build`.
3. Открыть `http://localhost:3000`; API доступен на `http://localhost:8000`.
4. Для проверок использовать `docker compose run --rm backend python manage.py test` и `cd frontend && npm run build`.

Production-конфигурация описана в `docker-compose.prod.yml`; секреты должны поступать только из локального/server `.env` и не храниться в Git.
