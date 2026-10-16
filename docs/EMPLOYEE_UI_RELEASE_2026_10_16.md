# Выпуск страниц доступа и карточек чек-листов — 16.10.2026

Пользователь явно разрешил commit и публикацию; изменения отправлены в GitHub.
[PR #9](https://github.com/JohnyRiddle/ays_connect/pull/9) merged:
`eaabe27cf4a45d21dae92d6d7628a9a5d445093c`.
Feature `81f85ac`, итоговая сборка `0152e0677c0fc98e281663d6e330e07579d46db9`.

## Что опубликовано

- Отдельные `/people/employees/{id}/objects` и `/access`, меню «Настройки
  сотрудника» в карточке, возврат и взаимные ссылки.
- Поиск объектов/ролей/групп, группировка повторных ролей с числом назначений,
  понятные названия scope, удобная мобильная раскладка.
- Поиск и ограниченная высота списка объектов в прежнем редакторе назначений.
  Его API/payloads и checks `can_manage` сохранены.
- Чек-листы задач оформлены отдельными карточками с контрастным фоном,
  рамкой, оранжевым левым акцентом и иконкой заголовка; логика ответов сохранена.

## Проверки

Employee browser **4/4 PASS**, checklist browser **12/12 PASS**, включая
светлую/тёмную темы на 1280/390 px. TypeScript/Vite/diff check PASS.
Сценарии проверяют переходы/reload, поиск и пустой результат, 51 одинаковое
назначение одной строкой, read-only/отказ API, прежний scoped POST payload.

После публикации HTTPS **16 PASS** на обоих доменах: страницы, новые deep links,
health и SHA256 index/JS/CSS. Backend health.version остался `e24a928`.
Production browser **7/7 PASS**, **0 HTTP write attempts**: компактная карточка,
51 настоящее назначение Юлии одной ролью, OhMyGesh в поиске объектов,
reload отдельной страницы, mobile без overflow, контрастная карточка реального
чек-листа в светлой и тёмной темах. Core **7/7 healthy**.

## Публикация и восстановление

Frontend-only, опубликовано 16.10.2026 в **11:09:18 Новосибирск**.
Backend/deployment/compose source сравнен с действующей backend-версией:
изменений нет. БД, RBAC, permissions и миграции не менялись; полный backend
прогон не повторялся, потому что backend image не менялся.
Compose overlay меняет только image сервиса frontend_assets. Новые assets
копируются, затем index заменяется атомарно; **25 прежних assets сохранены**.
Сервер, workers, DB и proxy сохранили container IDs и состояние. Простоя нет.

Перед заменой сохранён полный архив текущего frontend volume: **32 файла**.
Off-host EFS и серверный LUKS mirror сверены SHA256; архив распакован и
все восстановленные файлы сверены по размеру/хешу. Независимый DPAPI-носитель
ключа на F: проверен test-passphrase. Это точка отката интерфейса; БД и media
для этого frontend-only выпуска не восстанавливаются и не изменяются.
Владелец Иван, хранение 90 дней без автоматического удаления.

Защищённые source/configs/archive/proofs/screenshots:
`I:\AYS Connect\TaskPatch\employee-ui-release-20261016T040723Z`.
SHA256 архива интерфейса:
`04ca8e074018115b5bf0869f319cdba6bacf77088252064572e8982709f8411b`.
Frontend image:
`sha256:80e49d05774877d1251b8b948d676a6b94a8fab20e2015e484ec6ac1933fe49a`.
Backend image сохранён:
`sha256:38805b148addb2b3c804d8b76530dfaaa1ffb565634a847b632662fedfe2a006`.

Operational wrappers и frontend metadata приведены к новой сборке; backend RC
и source image в них сохранены. Telegram и receiver выключены. Три отложенных
Telegram-файла остаются untracked и в выпуск не вошли. Секреты, screenshots,
конфигурации и архивы не добавлялись в Git. Статус **DEPLOYED_ACCEPTED**.
