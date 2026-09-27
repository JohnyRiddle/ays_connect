"""Boolean-only scan of known synthetic Projects secrets, Audit/Outbox and staging logs."""
import json
import os
import re
import sys
from pathlib import Path
sys.path.insert(0,"/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from audit.models import AuditEvent
from events.models import OutboxEvent
assert os.environ.get("PEOPLE_ACCEPTANCE_MODE")=="1"
assert settings.DATABASES["default"]["NAME"]=="projects_acceptance" and settings.DATABASES["default"]["HOST"]=="db"
fixture=json.loads(Path("/staging-private/projects-fixture.json").read_text())
secrets=[settings.SECRET_KEY]+[value["password"] for value in fixture["actors"].values() if value.get("password")]
payload=json.dumps(list(AuditEvent.objects.values("old_values","new_values","metadata")),default=str)
payload+=json.dumps(list(OutboxEvent.objects.values("payload","last_error")),default=str)
logs=sys.stdin.read()
def unsafe(value):
    return any(secret and len(secret)>12 and secret in value for secret in secrets) or bool(re.search(
        r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}",value))
audits_ok=not unsafe(payload)
logs_ok=bool(logs) and not unsafe(logs)
print(json.dumps({"projects_audit_outbox_secret_scan":audits_ok,"projects_staging_log_secret_scan":logs_ok,
    "log_input_present":bool(logs),"scope":"known synthetic fixture passwords, signing key and JWT-shaped strings"}))
if not(audits_ok and logs_ok): raise SystemExit(1)
