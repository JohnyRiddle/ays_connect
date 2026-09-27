"""Boolean-only audit/outbox/log scan against synthetic staging secrets."""
import json, os, re, sys
from pathlib import Path
sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from audit.models import AuditEvent
from events.models import OutboxEvent
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE')=='1'
assert settings.DATABASES['default']['NAME']=='people_acceptance'
assert settings.DATABASES['default']['HOST']=='db'
secrets=[settings.SECRET_KEY]
for path in Path('/staging-private').glob('gate*.json'):
    obj=json.loads(path.read_text())
    secrets.extend(a['password'] for a in obj.get('actors',{}).values() if a.get('password'))
payload=json.dumps(list(AuditEvent.objects.values('old_values','new_values','metadata')),default=str)
payload+=json.dumps(list(OutboxEvent.objects.values('payload','last_error')),default=str)
logs=sys.stdin.read()
def unsafe(text):
    return any(s and len(s)>12 and s in text for s in secrets) or bool(re.search(r'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}',text))
audit_ok=not unsafe(payload);logs_ok=not unsafe(logs)
print(json.dumps({'audit_outbox_secret_scan':audit_ok,'staging_log_secret_scan':logs_ok,'log_input_present':bool(logs),'scope':'known synthetic fixture passwords, staging signing key and JWT-shaped strings; not a proof against all PII leakage'}))
if not (audit_ok and logs_ok and logs):raise SystemExit(1)
