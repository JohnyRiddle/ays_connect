"""Approved policy data only: importing this module never seeds or assigns roles."""
import json
from pathlib import Path


def load_policy():
    policy=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
    groups=[policy[key] for key in ('allowlist','excluded','conditional')]
    codes=[code for group in groups for code in group]
    if len(codes)!=len(set(codes)):
        raise ValueError('Duplicate or overlapping access policy codes')
    if policy['is_staff'] or policy['is_superuser'] or policy['auto_assign']:
        raise ValueError('Administrative or automatic grants are forbidden')
    return policy


def registry_difference():
    from .models import Permission
    policy=load_policy()
    expected=set(policy['allowlist']+policy['excluded']+policy['conditional'])
    actual=set(Permission.objects.values_list('code',flat=True))
    return {'missing':sorted(expected-actual),'unknown':sorted(actual-expected)}
