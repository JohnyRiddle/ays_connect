# Private feedback — local implementation, 21 October 2026

Base: `41c6de4c4b724238d9ab9f4c043dc2d6828debf2`, branch
`feat/private-owner-feedback`. Separate clone on ADMIN:
`C:\Users\riddl\Documents\Codex\2026-10-21\task-3\ays_connect`.
Publication authorized on 21 October 2026. Implementation commit
`160c8dd65a31d91ccb3d776c6deefd49bd7c03e9` pushed to
[draft PR #24](https://github.com/JohnyRiddle/ays_connect/pull/24).
Merge/deployment remain gated by server identity and backup/restore evidence.
Existing dirty OneDrive checkout untouched.

Implemented: header feedback button beside profile, improvement/bug selector,
text only (3000 maximum), recipient/Telegram disclosure, accessible native dialog,
validation, close/cancel, idempotent retry and owner history with pagination.
No screenshots, URL/query parameters or diagnostic data are collected by the form.

Server: additive feedback table/migration, active-employee submission, atomic
author/command UUID uniqueness, transactional audit/outbox metadata without body.
List/detail/retry and Django admin enforce the same owner identity predicate.
Other staff/superusers cannot read the body. Application-owner identity requires
the fixed email plus verified user ID AND employee UUID; missing/invalid pins
fail closed. Infrastructure/DB operators remain outside application ACL scope.

Delivery: private durable queue, independent of Notification/NotificationDelivery.
Existing TelegramBotClient and TelegramAccount are reused. Before sending, the
worker verifies getMe against AYS_ai_expert_bot and active owner private binding
(positive chat ID equal to Telegram user ID). No username-derived routing.
Atomic claim and per-attempt lease prevent parallel send and stale result writes;
owner/binding are rechecked after getMe. 429 retries with backoff. Network ambiguity,
5xx, interrupted sends and missing message ID become unknown, never blind resend.
Owner-only explicit retry requires confirmation of nonreceipt and warns of a
possible duplicate. Exactly-once Telegram delivery cannot be guaranteed across
provider acceptance and a lost acknowledgement.

New delivery is disabled by default. Future release must verify existing owner
IDs, set FEEDBACK_OWNER_USER_ID/FEEDBACK_OWNER_EMPLOYEE_ID, verify existing token
with `manage.py feedback_preflight --check-bot`, and separately approve enabling
FEEDBACK_TELEGRAM_ENABLED and running `manage.py deliver_feedback --loop`.
No production configuration was changed. Keep general Telegram notifications off.

Read-only production browser observation: the account menu identifies
Ливеринов Иван / ivan@ays-connect.ru. His notification settings show Telegram
«Не подключён». No link token was issued, binding created or preferences changed.
Verified user flow, if binding is approved: Настройки → Подключить Telegram →
Открыть Telegram → Start in the private bot chat; then verify redeemed binding.
Existing corporate receiver availability still needs verification before claiming
this flow succeeds. Do not replace its webhook or enable broad notifications.

Read-only SSH to ivan@109.237.109.58:40222 using existing ays_connect_deploy key
was rejected with Permission denied (publickey). Current server IDs/config and
actual Telegram transport are therefore NOT VERIFIED. No credential changes.
Historical recipient IDs were not used as current binding.

Validation:
- Django check, migration drift and TypeScript/Vite build PASS. Build warnings:
  Lucide use-client directives and main JS bundle larger than 500 kB.
- PostgreSQL 17.11: final 86/86 tests PASS in 51.512 seconds (feedback, notifications, accounts), including
  owner denial, other-superuser/admin denial, full-body isolation, validation,
  concurrent idempotent submit, concurrent workers, retries, ambiguous outcome,
  revoked binding, stale lease and sanitized one-shot worker output. An initial
  command-output test exposed connection cleanup inside a calling transaction;
  fixed by limiting cleanup to persistent loop mode, then the full targeted suite
  passed. Test database destroyed normally after the final run.
- Playwright synthetic API desktop 1280/mobile 390: final 8/8 PASS in 20.1 seconds; screenshots visually
  inspected for light form and dark owner history, no horizontal overflow.
- Fixed stale inline validation error, history-loading state isolation and preserving
  text lock when an ambiguous retry is throttled. Final tests include these cases.
- API responses use Cache-Control: private, no-store. Model permission grants,
  staff or superuser status do not bypass the pinned-owner predicate.
- git diff --check and whitespace checks on all new files PASS.
- Release validation on implementation commit 160c8dd: full backend PostgreSQL
  suite **761/761 PASS**, parallel=3, 214.027 seconds; UI **8/8 PASS**, 19.0 seconds;
  TypeScript/Vite/check/drift/diff PASS. Subsequent changes are documentation only.
  These are local tests, not external CI or production acceptance. Real Telegram
  delivery was NOT run.

Isolated temporary resources outside repository: feedback-postgres/ runtime,
feedback-pg/ synthetic cluster on 127.0.0.1:15443, feedback-browsers/ Chromium.
Vite for this checkout uses 127.0.0.1:13143. No shared service restarted.
Both task-owned servers were stopped after final checks; portable runtime files
remain outside Git for reproducibility.
Screenshots are synthetic only, in frontend/test-results (ignored).

## API and worker contract

All routes below use the existing active-employee JWT authentication:

| Method | /api/internal/v1/feedback/ suffix | Access / result |
| --- | --- | --- |
| POST | submit/ | Active employee; kind, text, command_id only; 201 new / 200 replay / 409 conflicting replay |
| GET | capabilities/ | Active employee; can_read boolean |
| GET | empty | Pinned owner only; paginated private list |
| GET | UUID/ | Pinned owner only; private detail |
| POST | UUID/retry/ | Pinned owner only; failed/unknown and literal confirmed_not_received=true |

Private body exists only in Feedback.text and authorized owner response/Telegram
payload. Shared audit/outbox contain event identity, never the body, provider
response, chat ID, token, query string, screenshot, IP or user-agent from this form.
Generic Notification records and existing Telegram delivery/claim endpoints are
not used. Unhandled metadata-only feedback.submitted outbox events may remain
pending under the existing event registry; delivery polls the private queue.

No automatic retry of ambiguous outcomes: owner must inspect the personal chat
first. Manual retry can still duplicate a message accepted by Telegram but not
acknowledged locally; the UI states this limitation. Safe 429/configuration waits
are durable and processed by the independent worker. Browser draft/idempotency
state is memory-only and survives modal close, not a full page reload.

## Reproduce local checks

Use an isolated PostgreSQL DATABASE_URL and never production for tests:

```text
python manage.py test feedback notifications accounts --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
node node_modules/typescript/bin/tsc
node node_modules/vite/bin/vite.js build
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 13143 --strictPort
node node_modules/@playwright/test/cli.js test --config playwright.feedback.config.ts
```

Browser tests route all API calls to synthetic responses. FEEDBACK_CHROMIUM can
select a local compatible executable; no real browser session/tokens are used.
Future release requires separate approval, verified server pins/config/receiver,
migration rehearsal and private owner delivery acceptance. This document is not
evidence of production deployment or real Telegram delivery.

## Release gate status after publication authorization

Fresh origin/main fetch still resolves to the base SHA above; GitHub reports the
PR mergeable and clean. This feature includes neither announcements nor iiko changes.
There are no tracked GitHub Actions workflows in this baseline. The GitHub App
cannot read the administration-only protection endpoint (403), but the allowed
ordinary branch endpoint confirms protected=false, protection.enabled=false,
required_status_checks.enforcement_level=off and empty contexts/checks. Rulesets
are empty. At implementation SHA: 0 statuses, 0 check-runs and 0 PR workflow runs.
External required CI is not configured; empty results are not a successful CI run.

Server stages are BLOCKED by the already observed SSH publickey rejection. No
retry, alternate key, access change or alternate server route was attempted after
that refusal. The existing runbook uses server-side Compose/backup/restore; there
is no verified independently available deployment path for this release.

Before deployment, an authorized operator must verify the existing owner IDs,
active account, bot identity/config and binding. Do not invent pins or deploy a
working-history claim with empty pins. Delivery remains disabled until its separate
recipient/config checks succeed. Do not enable old notification workers or send
production test feedback. No credentials/grants/security changes are authorized.

Server release plan (not executed):
1. Record the exact approved commit/images and required CI at that SHA.
2. Make a fresh protected DB/media/frontend backup using the existing approved
   storage/runbook; verify checksums and restore an isolated, egress-disabled copy.
3. Rehearse additive feedback.0001 migration on that copy, compare existing table
   counts and identity/RBAC fingerprints, repeat check/drift, and verify owner-only
   list/detail/admin using existing personas without additional grants.
4. Verify existing owner pins before exposing private history. Keep feedback
   Telegram disabled while binding/config/receiver are unverified.
5. Take and verify the frozen rollback point under the existing write-window
   procedure; switch immutable images/assets only after all applicable gates pass.
6. Production smoke is read-only: version/health/assets, owner history access and
   denied non-owner access. Do not submit test feedback or send employee messages.
7. Rollback by returning previous images/frontend assets while retaining the new
   feedback table and any writes. Never drop the table or restore an old database
   over new live data. Keep the independent feedback sender stopped.

Draft PR is the review artifact while these gates remain open; it is not proof of
a production release. No protected backup or production smoke has been performed.
