# Выпуск конструктора чек-листов — 14.10.2026

Опубликован feature RC `7d82e296320c5c4fef6ca671d671e5bf5d194157` на https://ays-connect.ru.
PR: https://github.com/JohnyRiddle/ays_connect/pull/4.

## Результат

Работа → Чек-листы: конструктор шаблонов с разделами, порядком, обязательными
пунктами, шестью типами ответов, предпросмотром, копированием и архивированием.
В задаче — прикрепление независимой версии, ответы с комментариями и прогресс;
незаполненные обязательные пункты блокируют завершение. Старые экземпляры не
переписываются изменениями шаблонов. Исправлены конфликт from-template/DELETE
и изменение завершённой задачи через устаревшее состояние.

Из аналитики убраны «Решено заявок», «SLA решения», «Backlog заявок».
Telegram выключен во всех семи core runtime; receiver не запускался и остаётся
остановлен. Отложенные три Telegram-файла не вошли в Git-коммит выпуска.

## Проверки

- Fresh-copy snapshot `2026-10-14T09:54:03.042171+00:00`: защищённая изолированная
  копия production, восстановлены 202 таблицы; внешние отправки выключены.
- Полный PostgreSQL backend **685/685 PASS**, parallel=3, production password
  hasher; это финальный feature RC, без локального ускоренного MD5.
- Все исходные строки/колонки 202 таблиц сохранены после init; план миграции
  только `work_tasks.0009_checklist_builder`, повторный план пуст.
- Реальные роли копии: owner создаёт шаблон, руководитель Технической службы
  получает задачу и отвечает на все шесть типов; ноль/False принимаются,
  обязательные пункты блокируют завершение, stale answer даёт 409,
  готовая задача защищена. 9/9 проверок, все fixture writes ROLLBACK.
- Локальные Playwright **4/4 PASS**, TypeScript/Vite, Django check и migration
  drift PASS; публикуются immutable images из Git archive feature RC.
- Production: **14 HTTPS 200**, оба домена, точный hash index
  и версия backend; **7/7 healthy**. API smoke после миграции повторён в
  production с ROLLBACK всех проверочных записей.
- Actual HTTPS UI под owner: конструктор/предпросмотр, четыре показателя задач
  без показателей заявок, мобильный конструктор без overflow. **3/3 PASS**,
  **0 HTTP writes**. JWT только в памяти, без refresh/login DB-записей.
- После возобновления workers неизменны 10 таблиц пользователей, People,
  ролей/прав и импортированной оргструктуры. Испытательные контейнеры остановлены.

## Публикация и восстановление

Успешное окно закрытого ingress: **81.016 с**.
Frozen UTC: `2026-10-14T10:03:57.228326+00:00` (Новосибирск: 14.10.2026 17:03:57).
DB/media/frontend сохранены в EFS off-host и LUKS server mirror с совпадающими
SHA256; off-host dump восстановлен в отдельную DB, 202 таблицы PASS;
media/frontend извлечены и проверены по полному файловому manifest.
Ключ LUKS восстановлен с отдельного DPAPI носителя и test-passphrase PASS;
plaintext key-файлов нет. Ответственный за recovery — Иван, хранение 90 дней,
автоматическое удаление не добавлялось.

| Файл | SHA256 |
|---|---|
| database.dump | `db66c4a70aa07a494d4e5342fda6b89a88e6d58c6d66e4d892331a3d801986bd` |
| media.tar.gz | `740d336fb437270b82d742c0c2bf348156b4eb1eeff4c19773703aef9003a503` |
| frontend.tar.gz | `539e31dbb4359b625abd9b9f5dd68e3bf1ace8f4d1af03ad0af551e0abbdcaf1` |

Backend/worker image: `sha256:695b28b7bf2962f65db3fa06b245b73d0b7154e444478e6f52f6f5720f90af5a`.
Frontend image: `sha256:bf96015363f8ce1fda945c1ac32899d4b50bd11715787637337f719bc98306cd`.
Evidence: `I:\AYS Connect\TaskPatch\checklist-release-20261014T095203Z`.
Server mirror: `/home/ivan/ays-pr3-release-d6b2a8126018/encrypted-rehearsal/mounted/restore-volumes/ays-checklists-20261014T095400Z/frozen-rollback-20261014T100335Z`.
Актуальная команда Compose: `/opt/ays-connect/compose-current.sh`.
Прежняя Telegram compose.sh также переведена на актуальный набор, чтобы будущее
подключение Telegram не вернуло старый backend. Secrets-файлы не менялись.
Предыдущие hashed frontend assets сохранены для открытых вкладок.

До maintenance локальная защита остановила первый запуск из-за отсутствующего
поля составного Compose в operational state (запись была перезаписана ранее
запущенным regression helper). Production не останавливался; pre-maintenance
evidence сохранён отдельно, state обновлён перед успешным переключением.

Миграция аддитивная. При отказе до открытия ingress предусмотрен возврат старых
images без downgrade БД; автоматический возврат в успешном окне не потребовался.
После открытия ingress не восстанавливать frozen DB вслепую: сначала закрыть
запись, сохранить новые DB/media/Audit/Outbox и подготовить совместимый возврат.
Production роли, сотрудники, объекты и существующие задачи не удалялись.
Документирующий commit после выпуска не меняет runtime code/images.
