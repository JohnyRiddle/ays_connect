"""Credential-safe HTTP smoke; retain synthetic records, never print tokens/passwords."""
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.db import transaction
from accounts.models import User
from employees.models import Employee
from employees.services import AccountAccessService

assert settings.DATABASES['default']['NAME'] == 'people_acceptance'
assert settings.DATABASES['default']['HOST'] == 'db'
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE') == '1'
assert os.environ.get('DJANGO_SECRET_KEY'), 'Run through /acceptance/runtime.py'
name = 'auth-http-' + secrets.token_hex(6)
password = secrets.token_urlsafe(32)
with transaction.atomic():
    actor = User.objects.create_user(username=name + '-actor', email=name + '-actor@example.test')
    user = User.objects.create_user(username=name, email=name + '@example.test', password=password)
    employee = Employee.objects.create(user=user, first_name='Synthetic HTTP', employee_number=name)

def request(path, payload=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/' + path,
        data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None

status, pair = request('login/', {'email': user.email, 'password': password})
assert status == 200, 'Initial login failed'
assert request('me/', token=pair['access'])[0] == 200
AccountAccessService.set_access(employee=employee, actor_user=actor, enabled=False, action='suspended')
assert request('me/', token=pair['access'])[0] == 401
assert request('refresh/', {'refresh': pair['refresh']})[0] == 401
AccountAccessService.set_access(employee=employee, actor_user=actor, enabled=True, action='restored')
assert request('me/', token=pair['access'])[0] == 401
assert request('refresh/', {'refresh': pair['refresh']})[0] == 401
status, fresh = request('login/', {'email': user.email, 'password': password})
assert status == 200, 'Fresh login failed'
assert request('me/', token=fresh['access'])[0] == 200
status, renewed = request('refresh/', {'refresh': fresh['refresh']})
assert status == 200, 'Fresh refresh failed'
assert request('me/', token=renewed['access'])[0] == 200
print('live_http_old_access_denied=PASS old_refresh_denied=PASS fresh_login=PASS')
print('synthetic_employee_id=' + str(employee.pk))
