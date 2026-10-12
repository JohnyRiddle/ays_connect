# Registration production release — 12 October 2026

## Identity and immutable artifacts

Runtime: `713be6b755950fcce5f5bf22d9fc05743c8f0053`. Base main: `5d9da353ee552af3b0c2182c374f132d0e91e2ce`.
Commit sequence: `f60780d` registration, `f330540` no verification/no mail,
`07c0343` earlier rehearsal evidence, `713be6b` reviewed AssignmentTarget integration
(10 files; no additional migration). This evidence commit changes documentation only.
GitHub HEAD/merge SHA are authoritative in [PR #2](https://github.com/JohnyRiddle/ays_connect/pull/2).
Merged backend/frontend runtime must equal this RC; merge does not run init again.

Pinned immutable **Docker image IDs**, not registry RepoDigests:

| Artifact | Image ID |
|---|---|
| backend/init/all six workers | `sha256:ff0e9533481448fedbc810600df18a63d75b1f4c4ebcd232ca2837d4ce467e1e` |
| frontend assets | `sha256:08ba6bc9662f572939f86e9e4aa83b11fe29cb6ecd31deaa919e368f13ea6129` |
| previous backend | `sha256:83c65c8816fcff3c09ea37482282edc13397fd67440dba8bb83d0eadfb98ffa6` |

Backend image built from exact committed backend archive over unchanged dependency
base; 433 source files verified. Frontend built from exact commit/lockfile with
`VITE_API_URL=/api/v1`, `VITE_APP_VERSION=713be6b755950fcce5f5bf22d9fc05743c8f0053`. Production current index/referenced
bundle equals immutable image manifest; old unreferenced hashed assets retained.
Pinned override preserves existing production env, iiko file, TLS/proxy, DB/Redis,
media/static/frontend bindings. Registration email delivery disabled. Actual source
production PostgreSQL: 17.11 (Linux/musl); runtime source 416 files matches base main.

## Final validation

| Command / evidence | Result |
|---|---|
| `python manage.py test --noinput` on isolated PostgreSQL 17.11 | **634/634 PASS**, 395.305s |
| `python manage.py test employees.test_registration employees.test_assignment_targets_api employees.test_onboarding employees.test_registration_upgrade --noinput` | **61/61 PASS**, 117.044s |
| `python manage.py check` | PASS |
| `python manage.py makemigrations --check --dry-run` | PASS, no drift |
| TypeScript and `npm run build` | PASS |
| `node node_modules/@playwright/test/cli.js test --config playwright.registration.config.ts` | synthetic desktop/mobile **6/6**, 13.9s |
| fresh restored copy API | **40/40 PASS**, rollback transaction, original rows/grants unchanged |
| committed browser assertions against immutable frontend and fresh copy | desktop/mobile **6/6 PASS**, 23.7s |
| copy/production actual init, migrate check, check/drift, repeated migration plan | PASS, repeat plan empty |
| final preservation of original User/Employee/Role/RolePermission/EmployeeRole/targets/Work tables | PASS, 27 tables |

Windows temporary browser file initially used CP1251, preventing Russian label
matching. Corrected test-harness encoding to UTF-8; assertions retained. Proxy harness
supports normal methods and Host; no runtime edits. Production SSH-only ingress
initially contained old embedded Objects frontend; replaced its read-only frontend
binding with the verified current volume before live UI acceptance. Launcher rejected
unsupported `compose run --no-build` before executing init (DB still 106); corrected
launcher, then actual production init executed once. Evidence does not promote failed
harness attempts to PASS. Full regression not repeated for this documentation commit.

## Snapshots, preservation and storage

Final online rehearsal snapshot: **2026-10-12T12:53:30.278133+00:00** (19:53:30.278 Novosibirsk).
DB/media exported read-only, off-host EFS files checked, restored into new LUKS-backed
volumes/internal network. No production mounts, published ports, restored workers or
external egress. Actual init `migrate --noinput && seed_permissions && collectstatic
--noinput && chown -R app:app /app/media /app/staticfiles` passed on the copy.
Original 198 tables' original IDs/columns preserved; email collision groups zero.
Only planned minimal role +2 catalog grants; no real EmployeeRole assignments added.

Immediately before maintenance: User 5, Employee 4, Role 2, RolePermission 127,
EmployeeRole 2, Location 3, Facility 0, Zone 0, AssignmentTarget 3; applied migrations
106. These values describe this actual production inventory, not a hypothetical DB.
After init, before smoke: User 5, Employee 4, Role 3, RolePermission 129, EmployeeRole
2, Location 3, targets 3, migrations 112. Existing rows preserved, not just counts.
After smoke: two explicitly marked inactive test accounts/Employees, retained targets,
one inactive test-only scoped role and revoked assignments, two archived test objects.
Original role/grant/user/employee/target/Work rows preserved. Number counters and token,
audit/event history may advance from authorized tests; no fixture history was deleted.

Fresh **frozen**, consistent rollback snapshot: **2026-10-12T13:18:22.743916+00:00**
(20:18:22.744 Novosibirsk). Public and restricted ingress closed, backend/six writers
stopped, periodic backup paused idle; client transactions and prepared transactions
zero. Fresh DB/media files did not overwrite old copies. Server raw files on confirmed
LUKS mapper, protected EFS off-host storage; checksums compared in both places:

| Frozen file | SHA-256 |
|---|---|
| DB | `99d7dc5ecebe60e8fb621c8aea7014dfd918eca2d59b947436839c31d0703549` |
| media | `63e15ba15ac544c6de0d349438e999d5025d7b1ff3accf7bf1e89577f4225d63` |

Restored **these off-host files** into new isolated encrypted volumes; original
fingerprints and full six-migration init/check/drift/empty plan PASS before production
init. Separate protected DPAPI recovery key freshly tested against LUKS in memory;
no plaintext key file. Backup guard SHA checked, correct mapper and free space verified;
retention stays disabled. Raw backup/copy volumes/evidence retained, containers stopped.
Backup copies retained at least 90 days, **not before 10 January 2027**; deletion only
by Ivan, including restore volumes. Recovery owner: Ivan. Key must remain recoverable
for every retained backup. Evidence/raw data/secrets stay outside Git.

EFS/LUKS at-rest protection is proved; BitLocker/whole-disk protection and historical
physical remanence are not claimed. Old unencrypted backups retained per explicit
instruction, never deleted. Snapshot populated media references: **0**; hashes and
missing references checked, populated-attachment compatibility remains untested.
Native PostgreSQL ownership/ACL adapted for isolated restore (`--no-owner --no-acl`);
Django grants preserved, native production ACL replication is not claimed.

## Migration and service acceptance

Exactly six migrations:

1. `accounts.0004_normalized_email`
2. `employees.0016_object_registration`
3. `employees.0017_registration_permissions`
4. `employees.0018_invitation_permission_snapshot`
5. `employees.0019_registration_shared_rate_limit`
6. `employees.0020_retire_registration_verification`

106→112. No AssignmentTarget schema change; no legacy Facility/Zone removal,
classification or mapping. Production init once, then pinned frontend/backend.
Old User/Employee/RolePermission/EmployeeRole/targets and business rows preserved.
`migrate --check`, check, drift and empty repeated plan PASS. Workers started in order:
recurrence, schedule, SLA, escalation, notifications, performance. Actual image IDs
match; backend + six workers healthy with fresh error-free heartbeats. Backup resumed,
confirmed idle guarded loop, retention disabled. DB/Redis/proxy bindings unchanged.

## Live acceptance and cleanup

SSH-only origin, normal existing owner login; no owner password/role/grant changes.
Owner UI approved marked self request with minimal viewer role. Public source returns
only UUID/name; pending login 401. API **27 checks +8 security checks PASS**, including
normal self/invite login, scoped list/detail/lookup/counts and related domains, denied
create/legacy API, scope-restricted delegation, fixed invite Location, bound email,
one-use and actual expired/revoked submission refusal (400/404, not rate-limit 429).
Expiration tested by shortening only a marked test invite timestamp with audit;
production clock, real invitations and real grants untouched.

A separate ordinary internal client used its actual source IP through restricted
ingress for additional invalid submits/tombstones; no spoofed forwarding or relaxed
throttles. Primary IP's sixth submit/tombstone hit normal 5/hour protection; confirm
and resend returned 410 on the ordinary secondary client. Active object-context invite
refused by legacy body-token validation/accept; no secret capabilities sent in URLs.
No bound email account created for revoked/expired/UI-revoked links.

Test account first had minimal rights (employee lookup 403), then a new test-only
role with location scope solely to marked object A for reviewer/delegation/employee
lookup. Scope list/count/search contained only A employees; object B/other data hidden.
No global scope, staff/superuser or edits to shared real roles. Responsibility mode
all did not expand access. Scoped assignment revoked, actual lookup 403 immediately.
Owner UI created/copied exact invite link to `https://ays-connect.ru/register` and
revoked it; token not published. Normal Work UI selected self employee as responsible
and invite employee as executor; no task created. Two new targets, replay/concurrency
covered by final tests; original targets/task links preserved.

Both test User/Employee pairs terminated via lifecycle, all temporary assignments
revoked, test role inactive, credentials/sessions/tokens invalidated. Each old access,
old refresh and new login returned **401**. Test objects closed/archived; public list
excludes them. Targets, audit, requests, invites and history retained. No direct SQL
delete. Cleanup still valid after workers. No test credentials in Git/log/chat.

Registered new internal consumers processed **25** state events; zero new registration
mail events and zero email/Telegram delivery attempts. Receipt is internal state
projection, not delivery. Historical five location events plus one genuine creation
on 12 October = **six original location events**, all pending/attempts 0 unchanged.
Six additional test location events and other existing/new legacy lifecycle types
without consumers remain pending, preserved and separately inventoried; no claim all
Outbox events are delivered/processed. They do not block registered registration events.
No automatic deletion/repair/reclassification was performed.

## Maintenance and current state

| Timestamp / duration | UTC |
|---|---|
| Maintenance begins | 2026-10-12T13:17:34.617828+00:00 |
| General ingress confirmed stopped | 2026-10-12T13:17:37.115418+00:00 |
| General ingress starts | 2026-10-12T13:45:49.994965214Z |
| HTTPS acceptance / maintenance ends | 2026-10-12T13:45:55.311097+00:00 |
| Measured interval ingress stopped | **1692.880 s (28m 12.880s)** |
| Maintenance interval | **1700.693 s (28m 20.693s)** |

This measures container-confirmed ingress closure, not independent external probe
latency. Both `ays-connect.ru` and `www.ays-connect.ru`: HTTPS `/`, `/register`, live
and ready 200; live version exact RC, index hash exact immutable bundle. Production
access open. Synthetic acceptance PASS; final restored rehearsal PASS; frozen rollback
restore/init PASS; live acceptance/cleanup PASS; deployment PASS. Merge follows this
evidence commit and is evidenced by PR #2, not inferred here.

## Operating instructions and recovery

Registration: <https://ays-connect.ru/register>. Management:
<https://ays-connect.ru/people/registration> (Employees → registration requests).
Ivan/existing superusers approve first release. Check person/email/object; select
minimal viewer role and explicit scope, then approve. To pre-approve, create invite
with object/role/scope/expiry, copy the link and transfer directly. Mail ownership is
not verified and no mail is sent. Existing ordinary-manager setup is not backfilled;
configure it separately through approved delegation. Responsibilities never imply RBAC.

After public writes or event processing, **never blindly restore the frozen backup**.
Close writes/writers, make and verify a fresh emergency DB/media/Audit/Outbox backup;
Ivan chooses forward repair or reconciliation of every new account, decision, record
and event before any restore. No automatic reverse migrations or overwrite of live DB.
Retain both checkpoints and current state. Before considering image rollback, verify
schema compatibility, block/deactivate temporary accounts and preserve all new data.

Remaining limits: no mailbox ownership proof by design; ordinary-manager rollout
not configured; populated media compatibility not exercised; legacy mapping/legacy
API access for new ordinary accounts remains blocked; unhandled old lifecycle/location
events retained; old unencrypted backup/remanence and whole-disk coverage not claimed.
Release does not authorize cleanup of those old backups or creation of real grants.
