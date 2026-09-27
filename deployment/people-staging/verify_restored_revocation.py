"""Retain synthetic pre-revocation tokens privately and test the restored database."""
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings

assert os.environ.get('PEOPLE_ACCEPTANCE_MODE') == '1'
assert settings.DATABASES['default']['HOST'] == 'db'
assert settings.DATABASES['default']['NAME'] == 'people_acceptance'
mode = sys.argv[1]
assert mode in {'prepare', 'verify'}
path = Path('/staging-private/restore-revocation-20260908c.json')
if mode == 'verify':
    settings.DATABASES['default']['NAME'] = 'people_business_restore_20260908c'

import django
django.setup()
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from accounts.models import User
from accounts.authentication import ActiveEmployeeJWTAuthentication
from accounts.serializers import EmailTokenSerializer, ActiveTokenRefreshSerializer
from employees.models import Employee
from employees.services import AccountAccessService

auth = ActiveEmployeeJWTAuthentication()
if mode == 'prepare':
    assert not path.exists(), 'Never replace a retained credential fixture'
    with transaction.atomic():
        suffix = uuid.uuid4().hex
        actor = User.objects.create_user(username='restore-actor-' + suffix, password=None)
        user = User.objects.create_user(username='restore-user-' + suffix,
                                       email='restore-' + suffix + '@example.test', password=None)
        assert user.pk != 2 and actor.pk != 2
        employee = Employee.objects.create(user=user, first_name='Synthetic restore')
        refresh = EmailTokenSerializer.get_token(user)
        access = str(refresh.access_token)
        assert auth.get_user(auth.get_validated_token(access)).pk == user.pk
        old_session_hash = user.get_session_auth_hash()
        AccountAccessService.set_access(employee=employee, actor_user=actor, enabled=False, action='suspended')
        AccountAccessService.set_access(employee=employee, actor_user=actor, enabled=True, action='restored')
        user.refresh_from_db()
        with path.open('x') as stream:
            json.dump({'user': user.pk, 'access': access, 'refresh': str(refresh),
                       'session_hash': old_session_hash, 'generation': user.auth_version}, stream)
        path.chmod(0o600)
    print('synthetic_pre_revocation_fixture=PASS')
else:
    fixture = json.loads(path.read_text())
    with transaction.atomic():
        user = User.objects.get(pk=fixture['user'])
        assert user.is_active and user.auth_version == fixture['generation'] > 0
        validated = auth.get_validated_token(fixture['access'])  # signature and expiry still valid
        try:
            auth.get_user(validated)
        except AuthenticationFailed:
            pass
        else:
            raise AssertionError('Restored old access revived')
        try:
            ActiveTokenRefreshSerializer().validate({'refresh': fixture['refresh']})
        except (AuthenticationFailed, TokenError):
            pass
        else:
            raise AssertionError('Restored old refresh revived')
        assert user.get_session_auth_hash() != fixture['session_hash']
        fresh = EmailTokenSerializer.get_token(user)
        assert auth.get_user(auth.get_validated_token(str(fresh.access_token))).pk == user.pk
        transaction.set_rollback(True)
    print('restored_old_access_refresh_session_denied=PASS fresh_generation_accepted=PASS writes_rolled_back=PASS')
