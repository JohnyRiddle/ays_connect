# Серверное развёртывание iikoCard

## Исправление food-limit-20260910

Сумма питания ограничена 10000 на prepare/create и в форме. Развёрнуты образы
ays-connect-iiko-backend:food-limit-20260910 и ays-connect-iiko-frontend:food-limit-20260910.
Изменены только create_views.py, test_creation.py, IikoCardsPage.tsx и overlay с
тегами образов. Backup этих файлов: /home/ivan/ays-iiko-food-limit/before.tar.gz;
прежние образы 20260910 сохранены. Миграций нет. 102/102 серверных теста прошли,
HTTP400 на сумму 10000.01 проверен под JWT без создания операции. Интерфейс
index-CY4SoIdC.js опубликован. Workers не обновлялись.

## Фактический сервер

- https://ays-connect.ru/iiko-cards; SSH ivan@109.237.109.58:40222.
- Каталог /opt/ays-connect, compose project ays-connect-production.
- Основа 98c23a7+backup-hotfix, cards-dashboard 14a1bed, без Git checkout.
- Сервер новее локального HEAD: PostgreSQL 17, Caddy, production People/Work/
  Performance и workers. Не заменять его локальным деревом или compose целиком.

## Пакет 20260910

Собран на копии серверного кода с backend/iiko и тремя файлами SPA. Точечные правки:
settings.py, urls.py, seed_permissions.py, серверный main.tsx (/iiko-cards).
Существующий /cards-dashboard сохранён. В серверной iiko.0001 зависимость заменена
на существующую events.0002_outboxevent_failed_at_outboxevent_last_error_code_and_more;
локальная events.0002 не переносится.

Сборочная копия: /home/ivan/ays-iiko-release-20260910.
Пакет: /home/ivan/ays-iiko-server-patch.tar.gz, распаковка:
/home/ivan/ays-iiko-patch-20260910. IIKO_RELEASE_MANIFEST.json содержит SHA256
до/после для 35 файлов; прежние файлы сверены перед установкой.

Образы: ays-connect-iiko-backend:20260910, ays-connect-iiko-frontend:20260910.
Серверный docker-compose.iiko.yml дополняет существующий production compose:
backend/init, frontend_assets; gunicorn один worker, четыре threads, timeout и
graceful-timeout 300 сек. Внутрипроцессный limiter iiko требует одного worker.
Workers, Caddy, DB, Redis и volumes не заменяются.

Реквизиты backend: /home/ivan/.config/ays-connect/iiko-sheregesh.env, права 600,
вне репозитория; frontend/workers их не получают. Используется существующий
superuser ivan@ays-connect.ru; локальный пароль/учётная запись не переносятся.

## Backup и переключение

/home/ivan/ays-iiko-backup-20260910 содержит pg_dump custom format, source.tar.gz,
текущие frontend assets и закрытую копию конфигурации. pg_restore --list проверен.
Прежние образы: ays-connect-backend:pre-iiko-20260910,
ays-connect-frontend:pre-iiko-20260910.

Миграционный план — только iiko.0001–0007. Миграции и permissions запускаются
явно через кандидат backend с --no-deps. Backend/frontend_assets переключаются
также с --no-deps; init/демогенераторы/другие workers не запускаются попутно.
Smoke: health, авторизованный каталог и чтение iiko; без создания/удаления/пополнения.

Откат: прежние образы и frontend assets; добавленные таблицы не удалять.
После реальных операций iiko восстановление БД требует отдельной сверки:
откат кода не отменяет внешние начисления и удаления.

## Проверки

Выкладка завершена 10.09.2026. 100 тестов iiko и полный серверный gate 426/426
прошли на PostgreSQL; frontend image собран. Миграции iiko.0001–0007 применены,
iiko permissions зарегистрированы без расширения назначений обычных ролей.
HTTPS ready/iiko-cards/cards-dashboard отвечают HTTP200. Проверены JWT-аутентификация
серверного superuser, каталог и чтение карты 55100 (owner/comment/categories/wallet).
На сервере 0 операций записи: реальных созданий/удалений/пополнений не было.
Check --deploy прошёл без ошибок с двумя прежними предупреждениями HSTS
include-subdomains/preload; эти настройки в рамках релиза не менялись.
Локальный полный gate 204/205 имеет стороннее падение learning; эти изменения
не включены в пакет. Backend переключён, workers сохранили свои прежние образы.
