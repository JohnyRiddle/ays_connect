"""Representative synthetic append-only upgrade; dedicated DB only."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

assert connection.vendor == "postgresql" and connection.settings_dict["NAME"] == "objects_upgrade"
executor = MigrationExecutor(connection)
targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] not in {"organizations", "access_control"}]
targets += [("organizations", "0003_orgunit_description_orgunit_metadata_and_more"), ("access_control", "0002_initial")]
executor.migrate(targets)
apps = executor.loader.project_state(targets).apps
get = lambda app, name: apps.get_model(app, name)
User = get("accounts", "User")
user = User.objects.create(username="synthetic-upgrade", email="upgrade@synthetic.test", password="!", is_active=False)
Legal = get("organizations", "LegalEntity")
legal = Legal.objects.create(name="Synthetic LE", code="SYNTHETIC-UPGRADE")
Org = get("organizations", "OrgUnit")
org = Org.objects.create(name="Synthetic org", code="SYNTHETIC-UPGRADE", legal_entity=legal)
Location = get("organizations", "Location")
location = Location.objects.create(name="Synthetic existing", code="EXISTING-UUID-CODE", location_type="unknown-keep-exactly", legal_entity=legal)
child = Location.objects.create(name="Synthetic existing child", parent=location, location_type="unknown-child")
Employee = get("employees", "Employee")
employee = Employee.objects.create(user=user, first_name="Synthetic", employee_number="EMP-SYNTHETIC-UPGRADE", primary_location=location, legal_entity=legal, org_unit=org, is_demo=True)
assignment = get("employees", "EmployeeAssignment").objects.create(employee=employee, location=location, legal_entity=legal, org_unit=org)
Task = get("work_tasks", "Task")
task = Task.objects.create(number="TASK-SYNTHETIC-UPGRADE", title="Synthetic linked Work", author=employee, created_by=user, updated_by=user, location=location)
project = get("projects", "Project").objects.create(number="PRJ-SYNTHETIC-UPGRADE", name="Synthetic linked project", location=location, created_by=user, updated_by=user)
Company = get("organizations", "Company")
company = Company.objects.create(name="Synthetic legacy", short_name="SYNTHETIC", is_demo=True)
region = get("organizations", "Region").objects.create(company=company, name="Synthetic region")
cluster = get("organizations", "Cluster").objects.create(region=region, name="Synthetic cluster")
facility = get("organizations", "Facility").objects.create(cluster=cluster, name="Synthetic legacy facility", facility_type="office", address="Synthetic address", is_demo=True)
zone = get("organizations", "Zone").objects.create(facility=facility, name="Synthetic legacy zone")
legacy_link = get("employees", "EmployeeFacility").objects.create(employee=employee, facility=facility)
ids = {"location": location.pk, "child": child.pk, "employee": employee.pk, "assignment": assignment.pk, "task": task.pk, "project": project.pk, "facility": facility.pk, "zone": zone.pk, "legacy_link": legacy_link.pk}
executor = MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
from organizations.models import Location as CurrentLocation, Facility, Zone
from employees.models import Employee as CurrentEmployee, EmployeeAssignment, EmployeeFacility
from work_tasks.models import Task as CurrentTask
from projects.models import Project
current = CurrentLocation.objects.get(pk=ids["location"])
assert current.code == "EXISTING-UUID-CODE" and current.location_type == "unknown-keep-exactly"
assert current.node_kind == "unclassified" and current.business_type == "" and current.business_status == ""
assert CurrentLocation.objects.get(pk=ids["child"]).parent_id == current.pk
assert CurrentEmployee.objects.get(pk=ids["employee"]).primary_location_id == current.pk
assert EmployeeAssignment.objects.get(pk=ids["assignment"]).location_id == current.pk
assert CurrentTask.objects.get(pk=ids["task"]).location_id == current.pk
assert Project.objects.get(pk=ids["project"]).location_id == current.pk
assert Zone.objects.get(pk=ids["zone"]).facility_id == ids["facility"]
assert EmployeeFacility.objects.get(pk=ids["legacy_link"]).facility_id == ids["facility"]
assert Facility.objects.get(pk=ids["facility"]).is_demo
executor = MigrationExecutor(connection)
assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
print("PASS: synthetic baseline upgrade, retained identities, UUID/code/free types/parents/People/Work/Projects/legacy links; repeat plan empty.")
