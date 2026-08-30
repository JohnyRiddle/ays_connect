# Phase 1.4A — Notification Core / In-App

Реализованы persistent intent/notification/delivery/attempt, templates, preferences, IANA quiet hours, allowlisted Outbox ingestion, safe rendering, inbox API, audit административных изменений и frontend bell с badge/dropdown/polling 45 секунд.

SLA migrations не изменены. Telegram/email/push не входят в фазу. Gate пройден на PostgreSQL 17.11: clean и legacy-data upgrade migrations, 164 backend-теста, 8-worker ingestion, concurrent delivery/SKIP LOCKED, Audit/Outbox rollback, Escalation → Inbox, Django checks, migration drift, diff check и frontend build.
