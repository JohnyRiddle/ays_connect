# Notifications Domain

`backend/notifications` — единственный production-владелец уведомлений. Поток: allowlisted `notification.requested` Outbox event → идемпотентный `NotificationIntent` → персональный snapshot `Notification` → centralized channel routing → `NotificationDelivery` → IN_APP/Telegram/Email handler → журнал `NotificationDeliveryAttempt`.

Уникальные DB constraints защищают event ingestion, recipient materialization и channel delivery. Шаблоны используют allowlist плоских переменных без `eval`, attribute/index traversal, format specifier и conversion. Для `SLA_ESCALATION` IN_APP обязателен и не задерживается quiet hours.

Inbox и channel settings ограничены текущим пользователем. Telegram binding использует hashed one-time token и secret-protected idempotent webhook. Template и delivery API защищены permissions `notification.template.view/manage` и `notification.delivery.view/manage`. Worker: `python manage.py process_notifications --batch-size 100 [--reconcile]`; PostgreSQL selection использует `FOR UPDATE SKIP LOCKED`, retries — backoff без sleep, максимум пять попыток. Ambiguous external outcomes переходят в `UNKNOWN` без автоматической повторной отправки.
