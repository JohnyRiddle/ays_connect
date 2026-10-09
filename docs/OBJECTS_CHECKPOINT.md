# Objects — точный checkpoint manifest, 08.10.2026

**READY FOR CHECKPOINT.** Функциональность реализована, synthetic acceptance PASS. **O0 DATA BLOCKED; реальные mapping, перенос и production readiness — NOT VERIFIED.** Commit/push/merge/deployment не выполнялись; staging index не изменялся.

## Идентичность проверенного diff

Worktree: `C:/Users/riddl/.codex/worktrees/objects/AYS Connect`; ветка `codex/objects`; HEAD/base `64f85fa58f06bf3eb8f24108e7dc2cfe8d998e85`. Нет Objects commits: рассматриваются tracked diff относительно HEAD и все перечисленные новые файлы, а не только git diff tracked.

Checkpoint message:

```text
feat(objects): add Location-based objects module and synthetic acceptance
```

Состав: **46 файлов**, 20 tracked изменений + 26 новых. **36 implementation/test/deployment файлов** проверены, SHA-256 ниже. Документация указана в составе, не входит в source fingerprint во избежание самоссылки evidence. Raw-byte fingerprint алгоритм: SHA-256 конкатенации UTF-8 строк `path + NUL + raw-file-SHA256 + LF` по сортированным source paths. Значение:

`4f03cee8c1da8559221e8875d152d6be2a495ed48aa4f3d3e53312d8c3fc1b63`

## Проверки окончательного состояния

Команды и evidence: [OBJECTS_ACCEPTANCE](OBJECTS_ACCEPTANCE.md). Выполнено 08.10.2026:

- fresh PostgreSQL full regression: 585/585, 163.202s, exit 0; внутри 36 Objects, 4 concurrency;
- inventory unittest: 8/8, exit 0, network none;
- frontend tsc/Vite: PASS, 1814 modules, index-DwZChlut.js / index-BBC6vgjQ.css;
- Chromium browser: 6/6, 28.9s, exit 0; desktop/mobile, committed-response-loss retry, version refresh, hidden FK preservation, rights/lifecycle/Work/Request/Project;
- manage.py check: 0 issues; makemigrations --check --dry-run: No changes detected;
- dedicated Compose config --quiet и git diff --check: exit 0;
- повторный read-only verify_restore.py для objects_upgrade/objects_restored: одинаковые 198 tables/1127 rows, data/trigger hashes и relationships PASS. Schema review не менял; fresh test install проверен сейчас, отдельные upgrade/dump/restore сделаны 02.10.

После этих gates менялась только документация manifest/acceptance. Runtime backend и UI соответствуют проверенному коду. Synthetic editor fixture и browser auth-cache helper вошли в финальный browser gate; login throttle не ослаблялся.

## Сохранность и исключения

Исходный checkout `C:/Users/riddl/OneDrive/Документы/AYS Connect` остаётся main/e03731c. До/после review сравнение SHA-256 всех его 13 modified/untracked файлов совпало: CURRENT_STATE, Cards/season sources/styles/data, две исходные project/cards docs и assets сохранены. Они **не включаются** из исходного checkout. Совпадение имени docs/CURRENT_STATE не означает перенос чужого изменения: в Objects worktree изменён только его собственный файл относительно base.

Не включать `.env`, DB/dump/media, frontend/node_modules/dist/test-results, Playwright traces/tokens, production/private inventory. Старые synthetic dump/fixtures не доказывают production состояние. `backend/service_requests/views.py` может отображаться M из-за line-ending/index-stat, но содержательный diff относительно HEAD пуст; файл **исключён** из checkpoint. Не использовать git add . или перенос всей исходной папки; точный allowlist ниже.

Границы: Work/People/Projects/Requests общие изменения — только availability hooks/selected Location/termination responsibilities. CORS Idempotency-Key и безопасный error envelope необходимы Objects UX; проверены полным regression. Нет массовой классификации/переноса Facility/Zone, новых connectors, M2M Projects или новых задачников.

## Полный allowlist

M — содержательное изменение tracked файла; A — новый файл, пока untracked. Hash `—` только у документации; source fingerprint покрывает каждый прочий файл.

| Статус | Файл | Raw SHA-256 |
|---|---|---|
| A | `backend/access_control/migrations/0003_alter_rolepermission_scope.py` | `b75e9029d1273216c42b943caf3a2dc324c94e2aca2d4ca7ebe2128029362895` |
| M | `backend/access_control/models.py` | `3caf807ad46cc0ed7f47f4e41f3a68934b239b9086fca5749d5f78ec4bb8f89a` |
| M | `backend/access_control/services.py` | `bec47caab4c5c4e50d34c23058010a4165b3dc9de46abcaca6590e18ab8d43a8` |
| M | `backend/access_control/urls.py` | `f80b610cd9622eeab7e24154f56e8b43d3e772b89b049a166aeefed5bd6e69fa` |
| M | `backend/config/exceptions.py` | `2b689167c27f9657ed8bbc5a9880218a1fe881df7c57e5102a78e008135e97fa` |
| M | `backend/config/settings.py` | `6a7483dbff31690fbfa71d71f580743b00e461e6e43a79fc94e0238b50cdff64` |
| M | `backend/employees/services.py` | `ffd874323e8a1c56c59a5b68441a38d6afe904a076dda49e077079e0a6cb9693` |
| M | `backend/employees/teams.py` | `a14588863c27cc239456582691ce8babffd319b6fbb5008759823b055fcdde7d` |
| M | `backend/organizations/admin.py` | `ad37d95887671f129fc33ab0ffc0e7fa208a4a47386958e738bd332f06485ca4` |
| M | `backend/organizations/internal_api.py` | `f3304e11d90ac8186eeccb20dc5269f23bc23e6c0fca3add1a6be8f8e44da94c` |
| A | `backend/organizations/migrations/0004_location_address_location_business_status_and_more.py` | `27fb9cc005742376443b7ffd3fdfc31e1e0832d906faad35adfd66b2fea20ad9` |
| A | `backend/organizations/migrations/0005_objects_guards_and_permissions.py` | `1645bf37e42d738fb53bfc73592acd1052d225385dba85f3ba7123eb3ed0fedd` |
| A | `backend/organizations/migrations/0006_responsibility_service_guard.py` | `0c03c17fc95a55097cce0235b6eff28467814dfaad6ac9e355d08202555aa718` |
| A | `backend/organizations/migrations/0007_binding_lifecycle_guards.py` | `5da64c498179a5ff3da444e1d85f7e9d873c415f8a9b314f88260347ac2899c1` |
| M | `backend/organizations/models.py` | `9046218b0b0e041795098aae6fc596464bdac31ec2e6d46d71d35b0017da553f` |
| A | `backend/organizations/object_policies.py` | `c6388dcfa9155a3d915785d626ebac21cc6fbd0d4323d3424d9c60d94b5dd233` |
| A | `backend/organizations/object_services.py` | `b7e73df9f57dc41b3cb897e1fd19e5e5d3b9b3e37d129be18b2698c1bef3b6a5` |
| A | `backend/organizations/objects_api.py` | `ac93a7734774ef619d69fb25696b02878150be1d56228671443dde38c12d297f` |
| A | `backend/organizations/test_objects.py` | `71e24d1e9790646e5b83334b4db925892599c9af45e1552bd0ecf506f9ad4b95` |
| M | `backend/projects/services.py` | `f0886adaba73b7ce186b36801c41f25dc8815572ae3c7f0bbb5be85290277c3d` |
| M | `backend/service_requests/serializers.py` | `69ff9e0e2a3c876a112df1908012006cc4917316bde3a5ee6dc043495bec6225` |
| M | `backend/service_requests/services.py` | `176463a48b58beffb3790642bd6f1aa7054301da2de464b49d5b01d6e14105ee` |
| M | `backend/work_tasks/automation.py` | `1d79df10252fe409747d124c285ed1dce1c9fe2c94691b511ce0fedaca4ec238` |
| M | `backend/work_tasks/services.py` | `c8748813f19f7fbe5f7b7e0a56e522b72c37b2a30916bbf01f7fa7a0a30cae08` |
| A | `deployment/objects-staging/compose.yml` | `010e2d9af861fc429a594c22077704b0c3ac176598e83cc318531200533afece` |
| A | `deployment/objects-staging/prepare_synthetic.py` | `38ec8cd70b9284fbcebb3cdc689ee1fa1e913b287973f916077e14780d804bb8` |
| A | `deployment/objects-staging/verify_restore.py` | `2a0fbca6eb391fe840c8fe96b73fe18f40fcb8192e681ed328456e823cd4be76` |
| A | `deployment/objects-staging/verify_upgrade.py` | `ce6fd52766401e4463b2f70ad6ecbbac4e55ffa0c2ceaa1b0ba5d169ed1bbb45` |
| A | `deployment/objects_inventory.py` | `cc48470845824bbae20ed29ae12bffb54f43bc43cd5fb9f682d03f60187ceb5d` |
| A | `deployment/test_objects_inventory.py` | `afa78f8ab09399e8cb0164597f39f9782f0dd3a09a4069ea2d0b5873983ca814` |
| M | `docs/CURRENT_STATE.md` | — |
| M | `docs/MASTER_ROADMAP.md` | — |
| A | `docs/OBJECTS_ACCEPTANCE.md` | — |
| A | `docs/OBJECTS_API.md` | — |
| A | `docs/OBJECTS_ARCHITECTURE.md` | — |
| A | `docs/OBJECTS_AUDIT_AND_PLAN.md` | — |
| A | `docs/OBJECTS_CHECKPOINT.md` | — |
| A | `docs/OBJECTS_O0_ACCEPTANCE.md` | — |
| A | `docs/OBJECTS_O0_CONTRACT.md` | — |
| A | `docs/OBJECTS_USER_GUIDE.md` | — |
| M | `frontend/src/main.tsx` | `21cd3fb7df8e48113b32106de4bbb384f14db6c8cee7b8cfbe7455e09c300daa` |
| A | `frontend/src/objects.css` | `560239cf26c384430c06bd4e1fd215deca2d387b59c1585145f6254ee2d9d4a6` |
| A | `frontend/src/objects.tsx` | `a49122a54c50c43a8ad1294e2914693bd9dd9bb97776ae26958aed4a65255833` |
| M | `frontend/src/work.tsx` | `e1b1da44604c88eb7bf467008eee2e758b04b51cbe420f7993230518bcb3db7c` |
| M | `frontend/src/workApi.ts` | `ab5e166301d8891a1ebfa67266dbad41cac5bad4add9aa0fd7f910c4232cf92d` |
| A | `frontend/tests/e2e/objects.spec.ts` | `d8ede8530e25d7f21c80b11609ea5f0d61a717786c46429aad54679ac170e91f` |
