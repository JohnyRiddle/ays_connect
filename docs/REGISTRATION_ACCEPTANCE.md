# Final registration acceptance — runtime 713be6b755950fcce5f5bf22d9fc05743c8f0053

Synthetic **634/634 PostgreSQL, targeted 61/61, browser 6/6 PASS**; TypeScript/build,
check/drift PASS. Final fresh restored production snapshot **2026-10-12T12:53:30.278133+00:00**: 198 original
tables/grants/targets preserved, full six-migration init 106→112, API **40/40**, pinned
frontend desktop/mobile **6/6, 23.7s**. Fresh frozen rollback **2026-10-12T13:18:22.743916+00:00** off-host
restore/full init PASS. Live **27 API +8 security checks and normal owner UI PASS**;
cleanup access/refresh/new login 401 for both accounts. Workers/registered Outbox,
backup and HTTPS PASS; deployment PASS. Merge is evidenced by PR #2 after the release
commit. No re-run of unchanged runtime after documentation/merge.
[Commands, artifacts, exact scope and limits](REGISTRATION_RELEASE.md).

Following sections record earlier RCs. Their counts and NOT PERFORMED states are
historical; they must not replace the final evidence and must not be called final PASS.

Свежая working DB rehearsal: **PASS for snapshot 12.10.2026 11:40:14.426 UTC**;
198 original tables/users/grants preserved, actual full init six migrations,
API 38/38, browser 6/6 18.3s, no SMTP. Production readiness CONDITIONAL, deployment
NOT PERFORMED. Scoped manager setup absent; existing superuser route available.
[Exact snapshot/SHA/image/limits](REGISTRATION_REHEARSAL.md).

# Registration acceptance — новая политика 12.10.2026

Ветка codex/registration, main base 5d9da353ee552af3b0c2182c374f132d0e91e2ce.
Требования заменяют email-verification/SMTP evidence коммита f60780d. Прошлый
626/626 и browser 6/6 относятся к прошлому контракту и не являются gate новой версии.
Production регистрации NOT PERFORMED; restored working DB compatibility NOT VERIFIED.
SMTP исключён из условий выпуска, владение адресом не подтверждается.

## Окончательные проверки

Изолированный PostgreSQL 17.11 / loopback 55443, synthetic DB и отдельная test DB;
без production mounts/accounts/integrations. Docker недоступен, PostgreSQL проверяется
напрямую. Dependencies — backend requirements/frontend package-lock. Evidence вне Git.

| Команда/проверка | Результат |
|---|---|
| `python manage.py test employees.test_registration employees.test_registration_upgrade --noinput` | PASS 42/42, 92.068s |
| `python manage.py test --noinput` | PostgreSQL полный regression **627/627 PASS, 408.376s** |
| `python manage.py check` | PASS |
| `python manage.py makemigrations --check --dry-run` | PASS |
| `python manage.py migrate --plan` после init | PASS, no planned operations |
| TypeScript + Vite build | PASS, 1816 modules |
| `node node_modules/@playwright/test/cli.js test --config playwright.registration.config.ts` | PASS 6/6, 13.5s, desktop/mobile; email disabled/host empty |

## Матрица

- Self submit immediately pending; email обязательный/нормализованный; до approval
  нет User/Employee, login 401. Decision authorised, reject reason/actor, status/cancel.
- Invite submit directly approved: one-use, bound email match, immutable Location/
  plan, expiry/revoke/reissue; old activation cannot bypass. No SMTP dependency.
- Repeat/parallel same email/one invite/competing emails: один User/Employee/primary/
  role, нет перезаписи ФИО/пароля и раскрытия оригинального capability.
- scoped lists/detail/options/counts/filter/delegation; changed role/inactive issuer/
  closed or archived Objects rejected. Related People/Work/Requests/Projects denied,
  new ordinary accounts have legacy endpoints closed, old accounts unchanged.
- primary employment history, selected/all responsibility separate from RBAC;
  existing Employee explicit link/returning lifecycle; grants unrelated preserved.
- Both flows create zero mail events even with email-enabled settings; tombstone
  mail consumer never calls provider, old jobs terminal failed/retry=None.
- Upgrade retires old object email_pending with Audit/Outbox, no autoactivation;
  legacy pending preserved, password hash cleared; existing UUID/grants/history
  synthetic upgrade preserved. confirm/resend 410, no side effects.

Шесть additions: accounts0004 + employees0016–0020. Исторические поля verification
сохранены, новый runtime ими не открывает доступ. Никакой Facility/Zone классификации,
mapping/переноса и automatic all. Internal Outbox receipts не объявляются mail delivery.
Browser assertions проверки поведения сохранены, SMTP/verification helpers удалены.

## Обязательные release gates

Свежая согласованная защищённая production DB/media/off-host restore в изолированном
контуре; collision check, actual migrate/seed/collectstatic/check/drift/repeat plan;
сохранность реальных пользователей и RolePermission/EmployeeRole/primary history;
настройка scoped approvers/delegation/default role. Runtime deployment/merge не выполнены.
Внешняя SMTP-доставка НЕ release gate. Полный GO/STOP/rollback:
[REGISTRATION_IMPLEMENTATION.md](REGISTRATION_IMPLEMENTATION.md).
Исходные dirty-файлы должны оставаться вне checkpoint. Полный актуальный состав и
нормализованные SHA-256 обновлены в REGISTRATION_CHECKPOINT.json.

Final source unchanged после gates; full log SHA-256: `79f6c863303653721b09d65884c4f5f930452d5cd23eb2542efb6503b525f646`. Evidence 12.10.2026, no commit/push/deployment in this follow-up. Новая схема с 0020 и политика отмены старых подтверждений должны быть проверены на свежей рабочей копии до выпуска.
