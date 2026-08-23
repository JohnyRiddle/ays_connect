# Текущее состояние AYS Connect

**Обновлено:** 23.08.2026

**Ветка:** `main`
**Remote:** `origin` → `https://github.com/JohnyRiddle/ays_connect.git`

## Текущая задача

Подготовка универсальной синхронизации проекта через GitHub и восстановления контекста Codex на другом компьютере.

## Сделано

- production-фазы People Core 1.1A, Tasks 1.1B–1.1D и Service Catalog 1.2A;
- permissions, Audit и transactional Outbox;
- динамические поля, access rules и immutable schema snapshots;
- проект опубликован в `origin/main` коммитом `bfe8313` до текущего обновления документации;
- добавлены проектные документы передачи контекста и универсальные инструкции Codex.

## Осталось

- проверить и закоммитить текущие изменения документации после подтверждения пользователя;
- начать Phase 1.2B только по отдельному техническому заданию;
- перед развёртыванием поверх старой базы подготовить план миграции существующих bigint ID к актуальным UUID-моделям либо использовать чистую базу.

## Известные проблемы и риски

- локальный Docker PostgreSQL volume создан ранним прототипом и не должен обновляться без резервной копии/плана данных;
- production и legacy Tasks временно сосуществуют;
- реальные Request lifecycle, routing, assignment, SLA и attachments ещё отсутствуют.

## Рекомендуемый следующий шаг

Проверить изменения документации, затем по подтверждению создать commit синхронизации. Следующая продуктовая разработка — Phase 1.2B.

## Команды проверки

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test

cd ../frontend
npm run build

cd ..
docker compose run --rm backend python manage.py test
```
