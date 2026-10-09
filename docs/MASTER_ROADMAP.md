# AYS Connect — текущий roadmap

1. People local staging Acceptance — PASS 15.09.2026; [evidence](PEOPLE_STAGING_ACCEPTANCE.md). Forgotten-password — отдельный product gap.
2. Projects first release — реализация в `codex/projects` на People checkout, локальный Quality Gate PASS 15.09.2026; [evidence](PROJECTS_ACCEPTANCE.md), [план](PROJECTS_IMPLEMENTATION_PLAN.md). Production release и commit/push не выполнялись.
3. Work dependency engine и метрика задач, блокируемых зависимостями — отдельное product-продолжение; в первый релиз Projects не входит по ТЗ.

4. Objects — функциональность реализована; финальное review **READY FOR CHECKPOINT**, 08.10.2026. Synthetic acceptance **PASS**: PostgreSQL 585/585, Objects 36 в этом наборе, inventory 8/8, browser 6/6, build/check/drift и restore fingerprints. **O0 DATA BLOCKED; реальные mapping, перенос и production readiness — NOT VERIFIED.** Следующий data этап — подтверждённая read-only инвентаризация и подготовка кандидатов, затем решение неоднозначностей. [Acceptance](OBJECTS_ACCEPTANCE.md), [точный checkpoint manifest](OBJECTS_CHECKPOINT.md), [O0](OBJECTS_O0_ACCEPTANCE.md). Commit/push/merge/deployment не выполнялись.
