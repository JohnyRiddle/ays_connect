"""Verify the integrated release upgrade from the production migration cutoffs.

Run only against a disposable PostgreSQL database.  The script never calls iiko
or any other external integration and stores synthetic identifiers only.
"""

from __future__ import annotations

import os
import uuid

import django
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor


EXPECTED_DB = os.environ.get("INTEGRATED_UPGRADE_DB", "integrated_upgrade_20260927")
PRODUCTION_CUTOFFS = {
    "accounts": "0002_initial",
    "employees": "0012_seed_profile_permissions",
    "work_tasks": "0003_alter_task_source_type_taskrecurrencerule_and_more",
    "iiko": "0007_cardcreation_topup_amount_and_more",
}


def require_disposable_database() -> None:
    name = connection.settings_dict["NAME"]
    if name != EXPECTED_DB or not name.startswith("integrated_upgrade_"):
        raise RuntimeError(
            f"Refusing to run against database {name!r}; expected disposable {EXPECTED_DB!r}"
        )


def production_targets(executor: MigrationExecutor):
    targets = []
    for app_label, migration_name in executor.loader.graph.leaf_nodes():
        if app_label == "projects":
            continue
        targets.append((app_label, PRODUCTION_CUTOFFS.get(app_label, migration_name)))
    return targets


def create_pre_upgrade_data(apps):
    User = apps.get_model("accounts", "User")
    Employee = apps.get_model("employees", "Employee")
    Task = apps.get_model("work_tasks", "Task")
    CardCreation = apps.get_model("iiko", "CardCreation")
    KnownGuest = apps.get_model("iiko", "KnownGuest")

    user = User.objects.create(
        email="integrated-upgrade@example.invalid",
        first_name="Synthetic",
        last_name="Upgrade",
        is_active=True,
    )
    employee = Employee.objects.create(
        user_id=user.pk,
        first_name="Synthetic",
        last_name="Employee",
        status="active",
    )
    task = Task.objects.create(
        title="Synthetic pre-upgrade task",
        description="Disposable upgrade fixture",
        status="in_progress",
        priority="normal",
        acceptance_policy="author",
        author_id=employee.pk,
        created_by_id=user.pk,
        updated_by_id=user.pk,
    )
    creation = CardCreation.objects.create(
        id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
        connection_id="sheregesh",
        organization_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        card_digest="a" * 64,
        request_digest="b" * 64,
        actor_id=user.pk,
        status="succeeded",
    )
    guest = KnownGuest.objects.create(
        connection_id="sheregesh",
        organization_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        customer_id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        name_digest="c" * 64,
    )
    return {
        "user": user.pk,
        "employee": employee.pk,
        "task": task.pk,
        "creation": creation.pk,
        "guest": guest.pk,
    }


def verify_post_upgrade(apps, ids) -> None:
    User = apps.get_model("accounts", "User")
    Employee = apps.get_model("employees", "Employee")
    Task = apps.get_model("work_tasks", "Task")
    CardCreation = apps.get_model("iiko", "CardCreation")
    KnownGuest = apps.get_model("iiko", "KnownGuest")
    Project = apps.get_model("projects", "Project")
    ProjectStage = apps.get_model("projects", "ProjectStage")
    ProjectTaskLink = apps.get_model("projects", "ProjectTaskLink")

    user = User.objects.get(pk=ids["user"])
    employee = Employee.objects.get(pk=ids["employee"])
    task = Task.objects.get(pk=ids["task"])
    creation = CardCreation.objects.get(pk=ids["creation"])
    guest = KnownGuest.objects.get(pk=ids["guest"])

    assert user.email == "integrated-upgrade@example.invalid"
    assert user.auth_version == 0
    assert employee.status == "active"
    assert task.title == "Synthetic pre-upgrade task"
    assert task.acceptance_policy == "author"
    assert task.acceptance_policy_locked is True
    assert creation.card_digest == "a" * 64
    assert creation.request_digest == "b" * 64
    assert creation.status == "succeeded"
    assert guest.name_digest == "c" * 64

    project = Project.objects.create(
        number="PRJ-UPGRADE-1",
        name="Synthetic upgrade project",
        status="active",
        manager_id=employee.pk,
        created_by_id=user.pk,
        updated_by_id=user.pk,
    )
    valid_stage = ProjectStage.objects.create(project_id=project.pk, name="Valid", position=1)
    other_project = Project.objects.create(
        number="PRJ-UPGRADE-2",
        name="Other synthetic project",
        status="active",
        manager_id=employee.pk,
        created_by_id=user.pk,
        updated_by_id=user.pk,
    )
    foreign_stage = ProjectStage.objects.create(
        project_id=other_project.pk, name="Foreign", position=1
    )
    ProjectTaskLink.objects.create(
        project_id=project.pk,
        stage_id=valid_stage.pk,
        task_id=task.pk,
        linked_by_id=user.pk,
    )
    try:
        with transaction.atomic():
            ProjectTaskLink.objects.filter(task_id=task.pk).update(
                stage_id=foreign_stage.pk
            )
    except IntegrityError:
        pass
    else:
        raise AssertionError("cross-project stage constraint did not reject the row")


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    require_disposable_database()

    executor = MigrationExecutor(connection)
    before = production_targets(executor)
    executor.migrate(before)
    old_apps = executor.loader.project_state(before).apps
    ids = create_pre_upgrade_data(old_apps)

    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    plan = executor.migration_plan(latest)
    expected_delta = {
        (migration.app_label, migration.name)
        for migration, backwards in plan
        if not backwards
    }
    required_delta = {
        ("accounts", "0003_user_auth_version"),
        ("employees", "0013_firstloginprogress_onboardinginstance_and_more"),
        ("employees", "0014_seed_onboarding_permissions"),
        ("employees", "0015_employee_account_access_state"),
        ("work_tasks", "0004_lock_acceptance_policy"),
        ("projects", "0001_initial"),
        ("projects", "0008_project_number_immutable"),
    }
    missing = required_delta - expected_delta
    if missing:
        raise AssertionError(f"upgrade plan misses required migrations: {sorted(missing)}")

    executor.migrate(latest)
    new_apps = executor.loader.project_state(latest).apps
    verify_post_upgrade(new_apps, ids)

    final_executor = MigrationExecutor(connection)
    assert final_executor.migration_plan(final_executor.loader.graph.leaf_nodes()) == []
    print("INTEGRATED_UPGRADE_PASS")
    print(f"from_targets={len(before)} applied_delta={len(expected_delta)}")
    print("external_integrations=disabled synthetic_data_only=true")


if __name__ == "__main__":
    main()
