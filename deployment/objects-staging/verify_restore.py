"""Read-only fingerprint and relationship checks for synthetic upgrade/restore DBs."""
import hashlib
import json
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db import connection, transaction
from organizations.models import Location, Zone
from employees.models import EmployeeAssignment, EmployeeFacility
from work_tasks.models import Task
from projects.models import Project

assert connection.vendor == "postgresql" and connection.settings_dict["NAME"] in {"objects_upgrade", "objects_restored"}
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        tables = sorted(connection.introspection.table_names(cursor))
        digest = hashlib.sha256()
        count = 0
        for table in tables:
            cursor.execute(f"SELECT row_to_json(t)::text FROM {connection.ops.quote_name(table)} t")
            rows = sorted(row[0] for row in cursor.fetchall())
            digest.update(table.encode())
            for row in rows:
                digest.update(row.encode())
                digest.update(b"\n")
            count += len(rows)
        cursor.execute("SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal ORDER BY tgrelid::regclass::text, tgname")
        trigger_digest = hashlib.sha256(json.dumps(cursor.fetchall()).encode()).hexdigest()
        cursor.execute("SELECT COUNT(*) FROM pg_trigger WHERE tgname IN ('ays_location_guard', 'ays_responsibility_guard')")
        assert cursor.fetchone()[0] == 2
    location = Location.objects.get(code="EXISTING-UUID-CODE")
    assert location.node_kind == "unclassified" and location.location_type == "unknown-keep-exactly"
    assert EmployeeAssignment.objects.filter(location=location).count() == 1
    assert Task.objects.filter(location=location).count() == 1
    assert Project.objects.filter(location=location).count() == 1
    assert Zone.objects.count() == 1 and EmployeeFacility.objects.count() == 1
    transaction.set_rollback(True)
print(json.dumps({"tables": len(tables), "rows": count, "data_sha256": digest.hexdigest(), "triggers_sha256": trigger_digest, "relationships": "PASS", "read_only": True}))
