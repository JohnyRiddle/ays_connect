"""Forward-only auth migration rehearsal in a dedicated synthetic database."""
import os
import sys

sys.path.insert(0, '/app')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings
upgrade_name = os.environ.get('PEOPLE_UPGRADE_DB', 'people_auth_upgrade')
assert upgrade_name in {'people_auth_upgrade', 'people_auth_upgrade_final'}
settings.DATABASES['default']['NAME'] = upgrade_name
import django
django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

assert connection.settings_dict['HOST'] == 'db'
assert connection.settings_dict['NAME'] == upgrade_name
executor = MigrationExecutor(connection)
latest = executor.loader.graph.leaf_nodes()
previous = [(app, '0002_initial' if app == 'accounts' else migration) for app, migration in latest]
applied = executor.loader.applied_migrations
if ('accounts', '0003_user_auth_version') in applied:
    raise SystemExit('Already upgraded; preserved database not downgraded. Use a new isolated database for a new rehearsal.')
executor.migrate(previous)
apps = executor.loader.project_state(previous).apps
User = apps.get_model('accounts', 'User')
Employee = apps.get_model('employees', 'Employee')
user = User.objects.create(username='auth-upgrade-synthetic', email='upgrade@example.test', password='!')
employee = Employee.objects.create(user_id=user.pk, first_name='Synthetic', employee_number='AUTH-UPGRADE-1')
identity = user.pk, employee.pk, employee.employee_number
executor = MigrationExecutor(connection)
executor.migrate(latest)
from accounts.models import User as CurrentUser
from employees.models import Employee as CurrentEmployee
current = CurrentUser.objects.get(pk=identity[0])
person = CurrentEmployee.objects.get(pk=identity[1])
assert current.auth_version == 0 and current.password == '!'
assert person.user_id == current.pk and person.employee_number == identity[2]
executor = MigrationExecutor(connection)
assert not executor.migration_plan(latest)
print('auth_upgrade_preserves_synthetic_identity=PASS repeat_migrate_noop=PASS')
