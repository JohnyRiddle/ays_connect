# Phase 1.4B — Telegram / Email Delivery

## Architecture

Business domains continue to publish semantic `notification.requested` events. `NotificationChannelRouter` records one diagnostic delivery per selected channel with a routing snapshot. The shared worker claims rows with PostgreSQL `SKIP LOCKED`; IN_APP, Telegram and Email handlers are isolated behind a registry.

Telegram and SMTP cannot guarantee exactly-once delivery after provider acceptance. Before a provider call the delivery records `provider_started_at`. A stale claim before dispatch is retryable; a stale claim after dispatch becomes `UNKNOWN / DELIVERY_OUTCOME_UNKNOWN` and is not resent automatically. Delivery attempts and sanitized provider metadata remain the source of truth.

## Telegram setup

1. Create a private-chat bot with BotFather.
2. Configure `NOTIFICATIONS_TELEGRAM_ENABLED=1`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_URL` and `AYS_CONNECT_PUBLIC_URL`.
3. Run `python manage.py configure_telegram_webhook`. The command never prints the token.
4. An authenticated employee opens Notification Settings, generates a short-lived link and follows the backend-provided `t.me` URL.
5. Telegram sends `/start <token>` to the protected webhook. Only the SHA-256 token hash is stored; tokens expire after 15 minutes by default and are one-time.

Webhook commands are limited to `/start`, `/status` and `/unlink`. User/chat numeric IDs are identity; username is display metadata. One active binding per Employee and Telegram user is enforced by PostgreSQL constraints.

## Email setup

Configure `NOTIFICATIONS_EMAIL_ENABLED=1`, Django `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` and `DEFAULT_FROM_EMAIL`. Recipient email is read from the canonical User profile. Phase 1.4B does not introduce email verification.

## Routing and quiet hours

- normal: IN_APP;
- warning/high: IN_APP + Telegram;
- critical: IN_APP + Telegram + Email;
- SLA escalation keeps mandatory IN_APP and bypasses Telegram quiet hours;
- other external delivery is deferred to the timezone-aware quiet-hours end;
- disabled channels, preferences and missing identities create diagnostic `SUPPRESSED` deliveries.

## Known limitations

- external provider delivery is at-least-once with best-effort duplicate prevention;
- ambiguous outcomes require operator review and are not blindly retried;
- Telegram supports private Employee chats only, not groups or task commands;
- no Push/SMS;
- real Telegram/SMTP smoke requires separately supplied credentials and public HTTPS infrastructure.

## Quality gate

PostgreSQL 17.11: clean migration PASS; upgrade from Phase 1.4A and preservation of template, notification/read state, delivery attempt, preference and quiet hours PASS. Notification tests 23/23; full backend 176/176; frontend production build PASS.
