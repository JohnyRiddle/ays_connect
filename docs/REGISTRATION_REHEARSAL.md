# Final RC rehearsal and release evidence — 713be6b755950fcce5f5bf22d9fc05743c8f0053

Final online snapshot **2026-10-12T12:53:30.278133+00:00**: original 198 tables/grants/targets preserved,
433 exact source files, PostgreSQL 17.11, six migrations 106→112, actual full init,
check/drift/empty repeated plan PASS; API **40/40**, immutable frontend desktop/mobile
**6/6, 23.7s**. Isolated internal network/blocked egress, no production mounts/workers.
Five copy-only users terminated, old access/refresh/new login 401, test object archived;
original users/grants unchanged; only original number counter advanced by fixtures.
Fresh frozen snapshot **2026-10-12T13:18:22.743916+00:00** independently restored from protected off-host
files and full init PASS before production init. Production then released and live
accepted, cleanup PASS. Exact hashes/images/commands and remaining limits:
[REGISTRATION_RELEASE.md](REGISTRATION_RELEASE.md).

The following is historical evidence for f330540; its 38/38, 18.3s and earlier
snapshot must not be attributed to final RC. Its pending release gates are superseded
only by the explicit final evidence above; it remains as an audit trail.

# Registration restored production rehearsal — 12.10.2026

Tested runtime RC `f3305408cc85d6d95db74706742499ceadb6c820`, draft [PR #2](https://github.com/JohnyRiddle/ays_connect/pull/2).
Production source image `sha256:83c65c8816fcff3c09ea37482282edc13397fd67440dba8bb83d0eadfb98ffa6`; RC rehearsal image `sha256:750faabd956daecc706f7c53aca7a8077db732cd6bd7172b4ce5fe4ee8bea657`.
Production backend 416/416 tracked Python/requirements hashes equal main
`5d9da353ee552af3b0c2182c374f132d0e91e2ce`; copy 431/431 equal exact committed RC.
Dependencies inherited from the verified source image, no dependency changes/downloads.

## Fresh snapshot / protected restore

Online repeatable-read exported snapshot observed **2026-10-12T11:40:14.426373+00:00**
(**12.10.2026 18:40:14.426 Asia/Novosibirsk**). Exact transaction opening instant was
not separately measured. pg_dump imported the same exported snapshot as baseline
fingerprints; read-only production transaction released after dump. Production
writers stayed running. Media was captured online separately: **not a frozen,
DB/media-consistent release rollback point**.

DB SHA-256: `07c00c43a8f25905dd380c57a886154239f56ba5f03682fbbf9da9c7016908dc`.
Media SHA-256: `740d336fb437270b82d742c0c2bf348156b4eb1eeff4c19773703aef9003a503`.
Fresh raw files saved directly to EFS off-host destination; per-file encrypted flags
and hashes verified. Restore consumed those off-host files, not the original stream.
Evidence: `I:\AYS Connect\Registration\ays-registration-20261012T113959Z`. Retain 90 days, deletion only Ivan; no old backup overwritten/deleted.

Server storage `/dev/mapper/objects-220ffac-recovery` verified in helper mountinfo;
new pg/media/static/tmp directories under existing LUKS storage. Dedicated volumes,
internal=true network; no production mounts/published ports/restored workers or
integration credentials, read-only API rootfs, encrypted /tmp. Two external TCP
probes denied. Copy secrets generated separately in mode-0600 files on LUKS, no
production secret copied into images/Git/chat. EFS/LUKS protection is verified at
file/logical-volume level; independent EFS certificate recovery and disk free-space
remanence were not retested here. Protection is not a claim of whole-disk encryption.

## Full init / preservation

Original restore fingerprints **198/198 tables PASS** before init. Collision groups=0.
Expected exact plan, then migrate/seed_permissions/collectstatic/chown:

- `accounts.0004_normalized_email`
- `employees.0016_object_registration`
- `employees.0017_registration_permissions`
- `employees.0018_invitation_permission_snapshot`
- `employees.0019_registration_shared_rate_limit`
- `employees.0020_retire_registration_verification`

Applied migrations **106→112**. Repeated plan [], check and model drift PASS;
static files 163. Every original row compared using its original
columns/ID, including UUID, User flags/auth_version/password hashes, Employee and
primary history. **198/198 original table rows preserved**, no legacy classification,
Facility/Zone conversion or existing all-responsibility assignment.

| Entity | Snapshot | After init |
|---|---:|---:|
| User | 5 | 5 |
| Employee | 4 | 4 |
| Role | 2 | 3 |
| RolePermission | 127 | 129 |
| EmployeeRole | 2 | 2 |
| Location | 3 | 3 |
| AssignmentTarget | 3 | 3 |

Only new minimal Role +2 RolePermission catalog rows; **no new real EmployeeRole**,
all original Role/RolePermission/EmployeeRole rows unchanged. New managed tables:
`employees_employeeobjectresponsibility`, `employees_employeeobjectresponsibility_locations`, `employees_registrationratebucket`.
Media restored hashes equal archive; populated file references **0**.
Attachment compatibility with populated media remains untested in this snapshot.

## API / browser / setup

Restored API **38/38 PASS**: email required/format, immediate self pending/no SMTP,
no User/login/work before approval, status, retired confirm/resend 410, scoped
review/options/detail/counts and approval; normal account then login, own-object
access/other-object hidden, related domains denied, legacy activation refusal,
immutable invite Location, bound email mismatch, direct invite activation/one-use,
forbidden scope expansion/all responsibility and zero mail events even SMTP-enabled.
API tests ran in rollback transaction; original rows/grants remained exact.

Same committed desktop/mobile browser assertions through SSH loopback and exact RC
frontend source: **6/6 PASS, 18.3s**. Only fixture imports/isolated URL guard adapted;
no assertions removed or exceptions suppressed. Verification helpers absent.
SMTP disabled/host empty. Real production owner password/session not used.

Snapshot has **1 active registration object**. **3 active superuser candidates**
(including existing owner User 1) can approve/delegate that object under current
policies. Existing administrator route technically available, minimal role eligible.
**Active scoped non-superuser approvers/delegators: none**. No real grants added to
make this pass. Scoped manager route proved on copy-only marked personas/objects;
ordinary-manager operating setup requires explicit role/scope assignment before use.
Retirement of object email_pending/mail jobs had no populated source rows in this
snapshot; that data transformation is covered by the synthetic upgrade gate.
Django RBAC preservation is proved; PostgreSQL ownership/ACL are adapted for the
isolated DB user (--no-owner/--no-acl), not a reproduction of production DB ACL.

Actual owner live login, manager production grants and production write-smoke are
**NOT PERFORMED** by this rehearsal.

After browser, 5 copy-only test User/Employee pairs terminated through lifecycle;
pre-cleanup access/refresh rejected after termination and new login denied. One test
object closed/archived, history retained. Original User/Employee/Role/grants hashes
still match; only original employee number counter changed due permitted copy-only
fixtures. Sequence allocations may advance during rolled-back tests, not production.
Copy containers stopped, restart=no, local tunnel/frontend stopped; evidence retained.
Backend/DB original container IDs/images unchanged; production HTTPS ready=200,
no downtime, production init/schema/grants/runtime not changed.

## Release status

Fresh restored DB upgrade/preservation **PASS for this snapshot**; API/browser
**PASS**. Full 627 and synthetic 42 gates belong to same runtime and were not rerun.
SMTP excluded from release conditions. Production readiness **CONDITIONAL**:

- Recheck live drift and decide actual administrator/scoped-manager operating setup;
  ordinary-manager grants are not configured and must not be assumed.
- Integrate the separately prepared Tasks employee AssignmentTarget automation
  (codex/task-assignees) before using newly created Employees in Work selectors;
  this RC preserves the three existing targets, does not include that separate fix.
- Prepare/verify pinned frontend artifact and reconcile production frontend drift;
  this rehearsal used exact RC source locally, did not switch/build production frontend.
- Before separately authorized release: closed write-window, fresh consistent
  protected DB/media rollback point, verified off-host restore, exact init/pinned
  services, authorized live smoke/worker checks. Online snapshot is not that point.
- Preserve new records on rollback; no blind restore after resumed writes.

Merge and production deployment **NOT PERFORMED**. This evidence must not be promoted
to live acceptance. Full plan: [REGISTRATION_IMPLEMENTATION.md](REGISTRATION_IMPLEMENTATION.md).
