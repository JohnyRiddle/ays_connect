"""Synthetic additive upgrade; no production fixtures or automatic mappings."""
from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class RegistrationUpgradeTests(TransactionTestCase):
    def test_normalized_email_collision_stops_upgrade_without_merging_users(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [(app, "0003_user_auth_version" if app == "accounts" else
                     "0015_employee_account_access_state" if app == "employees" else migration)
                    for app, migration in latest]
        executor.migrate(previous)
        old = executor.loader.project_state(previous).apps
        User = old.get_model("accounts", "User")
        first = User.objects.create(username="collision-one", email="collision@synthetic.test")
        second = User.objects.create(username="collision-two", email=" COLLISION@Synthetic.Test ")
        original = list(User.objects.filter(pk__in=[first.pk, second.pk]).order_by("pk").values())
        try:
            with self.assertRaisesMessage(RuntimeError, "Normalized email collisions: 1 groups"):
                MigrationExecutor(connection).migrate(latest)
            self.assertEqual(list(User.objects.filter(pk__in=[first.pk, second.pk]).order_by("pk").values()), original)
        finally:
            # Synthetic test fixture only; production migration never removes rows.
            User.objects.filter(pk=second.pk).delete()
            MigrationExecutor(connection).migrate(latest)

    def test_existing_identity_history_and_grants_are_byte_value_preserved(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [(app, "0003_user_auth_version" if app == "accounts" else
                     "0015_employee_account_access_state" if app == "employees" else migration)
                    for app, migration in latest]
        executor.migrate(previous)
        try:
            old = executor.loader.project_state(previous).apps
            User = old.get_model("accounts", "User")
            Employee = old.get_model("employees", "Employee")
            Location = old.get_model("organizations", "Location")
            Permission = old.get_model("access_control", "Permission")
            Role = old.get_model("access_control", "Role")
            RP = old.get_model("access_control", "RolePermission")
            ER = old.get_model("access_control", "EmployeeRole")
            Assignment = old.get_model("employees", "EmployeeAssignment")
            Request = old.get_model("employees", "RegistrationRequest")
            Invite = old.get_model("employees", "EmployeeInvitation")
            user = User.objects.create(username="upgrade-user", email=" Original@Synthetic.Test ", password="original-hash", auth_version=7, is_active=True)
            inactive = User.objects.create(username="upgrade-inactive", email="inactive@synthetic.test", password="disabled-hash", is_active=False)
            location = Location.objects.create(name="Unclassified original", code="LEGACY-UPGRADE", node_kind="unclassified")
            employee = Employee.objects.create(user=user, first_name="Existing", employee_number="EMP-UPGRADE", primary_location=location)
            Employee.objects.create(user=inactive, first_name="Terminated", employee_number="EMP-INACTIVE", is_active=False, status="terminated")
            role = Role.objects.create(code="upgrade-existing", name="Original role")
            permission = Permission.objects.create(code="upgrade.existing", name="Original permission")
            RP.objects.create(role=role, permission=permission, scope="global")
            ER.objects.create(employee=employee, role=role)
            Assignment.objects.create(employee=employee, location=location, is_primary=True, status="active")
            Request.objects.create(full_name="Legacy pending", email="legacy@synthetic.test", expires_at=timezone.now()+timedelta(days=7))
            Invite.objects.create(employee=employee, token_hash="f"*64, delivery_address="legacy@synthetic.test", created_by=user, expires_at=timezone.now()+timedelta(days=7))
            models = [User, Employee, Location, Role, RP, ER, Assignment, Request, Invite]
            baseline = {(model._meta.app_label, model._meta.model_name): list(model.objects.values()) for model in models}
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            current = executor.loader.project_state(latest).apps
            for key, rows in baseline.items():
                model = current.get_model(*key)
                for row in rows:
                    observed = model.objects.values(*row.keys()).get(pk=row["id"])
                    self.assertEqual(observed, row, key)
            self.assertEqual(current.get_model("employees", "EmployeeObjectResponsibility").objects.count(), 0)
            self.assertEqual(MigrationExecutor(connection).migration_plan(latest), [])
        finally:
            MigrationExecutor(connection).migrate(latest)
