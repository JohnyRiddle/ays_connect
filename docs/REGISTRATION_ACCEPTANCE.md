# Registration acceptance — 12.10.2026

Base: main `5d9da353ee552af3b0c2182c374f132d0e91e2ce`; branch `codex/registration`.
Runtime/schema implemented. Synthetic acceptance: PASS.
Working restored DB compatibility / external SMTP inbox: NOT VERIFIED.
Production deployment: NOT PERFORMED. iikoCard: separate phase.

## Contour and commands

Fresh PostgreSQL 17.11, loopback 127.0.0.1:55443, synthetic registration DB;
Django tests use a separate test_registration database. No production mounts,
users, roles, grants or integrations. Exact backend requirements and frontend
package-lock dependencies installed. Docker engine unavailable; PostgreSQL gate
ran directly against PostgreSQL, not SQLite. Raw fixture/evidence outside Git.

| Final-code check | Command | Result |
|---|---|---|
| Full backend regression | `python manage.py test --noinput` (DATABASE_URL points to isolated PostgreSQL) | PASS 626/626, 355.661s |
| Django | `python manage.py check` | PASS, no issues |
| Model drift | `python manage.py makemigrations --check --dry-run` | PASS, no changes |
| Repeat init migration plan | `python manage.py migrate --plan` | PASS, no operations |
| TypeScript | `node node_modules/typescript/bin/tsc` | PASS |
| Frontend bundle | `node node_modules/vite/bin/vite.js build` | PASS, 1816 modules |
| Desktop/mobile | `node node_modules/@playwright/test/cli.js test --config playwright.registration.config.ts` | PASS 6/6, 15.3s |
| Preservation | Private SHA-256 baseline comparison | PASS, 13 original dirty files + Objects CRLF-only views.py |

Full regression includes all existing modules plus registration/upgrade cases.
The prior 625/625 run preceded the last request-filter validation; it is historical,
not substituted for the final gate. Interrupted final attempts are not PASS.
Browser tests use exact local URL/DB guards and synthetic credentials, trace off.
Confirmation capabilities are generated within the synthetic fixture, not by
external inbox: browser email delivery is not claimed.

## Acceptance matrix

| Scenario | Evidence / limit |
|---|---|
| Signup, optional patronymic, password confirmation, no early working access | API tests + desktop/mobile self-registration |
| Email confirmation, approval/rejection/reason/actor, own status/resend/cancel | API tests; real local SMTP capture for verification |
| Invite UI, fixed Location/role/scope, bound optional email, one use / expiry / revoke / reissue | API tests + desktop/mobile invite/create/revoke |
| Normalized unique email and no automatic FIO matching | API tests + migration collision STOP |
| Explicit existing Employee link; returning normal User through lifecycle | API tests, UUID reuse, old grants revoked |
| Primary employment history; selected/all responsibility separate from RBAC | API tests; all includes future objects without extra access |
| Scoped list/detail/count/options; delegation, unsafe/default modified role rejection | API tests; unrelated grants preserved |
| Related People/Work/Requests/Projects denied; legacy IsAuthenticated bypass closed | API tests, real JWT legacy GET/POST denied, canonical own object available |
| Archive/close and inactive inviter | API tests, pending acceptance rejected |
| Concurrent submit / acceptance / invite reservation / shared throttle | PostgreSQL TransactionTestCase tests |
| Existing rows, UUID, identity, primary history and grants survive additive upgrade | Synthetic migration executor tests; repeat plan empty |
| Mail consumer success/retry/unknown/crash, state receipts | Tests including actual local SMTP protocol; receipt is not delivery |

Five additions: accounts 0004 + employees 0016–0019. No classification/mapping,
Facility/Zone deletion or data transfer. Projects change is only a Windows-safe
file/stream test cleanup; project runtime unchanged. Old public register and
invite-create contracts deliberately switch to object-based registration; old
issued legacy invite links retain their contract. Existing non-enrolled accounts
retain legacy behavior.

## Remaining release gates

- Restore fresh working DB/media in isolation; run collision preflight, complete
  init and compare real users/Employee/grants/history. Synthetic preservation
  does not prove populated production compatibility.
- Confirm external SMTP provider and inbox delivery, authorized approvers,
  default role and explicit delegation setup. Disabled/test email backends do
  not report delivery. Resolve UNKNOWN outcomes manually.
- All responsibility is installation-wide; multiple independent companies need
  a separate tenant contract. Legacy/global/org/legal/team grants cannot be
  transformed into Location scope by assumption. New ordinary accounts have
  legacy modules closed in this version.
- Follow protected backup/restore and pinned release plan in
  [REGISTRATION_IMPLEMENTATION.md](REGISTRATION_IMPLEMENTATION.md). Separate
  authorization required for production. No merge/deployment performed here.

## Checked diff

All task files are in the isolated codex/registration worktree: accounts identity
boundary; registration services/API/consumers/throttle; additive migrations;
People integration; existing notification worker; React screens; backend and
browser tests; implementation/user guide/acceptance/current state/roadmap.
No .env, DB/media, keys, raw backups or production credentials are included.
Exact checkpoint file names and normalized source SHA-256 are recorded in
REGISTRATION_CHECKPOINT.json; this manifest excludes itself.

Final evidence recorded 12.10.2026, 07:34 UTC. Full backend log SHA-256: `3fae1a923ca63b8504e5362c81d5969b0f7c195c1dc583732f074f40cc43d41d`. Test DB left by the interrupted run was recreated by `--noinput`; the successful final test run completed with exit 0 / OK. No runtime/schema edits after final gates.
