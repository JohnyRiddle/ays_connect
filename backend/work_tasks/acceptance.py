"""Acceptance type is mutable only before the first publication, in draft."""
from functools import wraps
from django.db import IntegrityError, transaction
from .exceptions import TaskValidationError

ERROR_CODE = 'task_acceptance_policy_frozen'


def validate_policy_change(task, value):
    if value != task.acceptance_policy and (task.acceptance_policy_locked or task.status != 'draft'):
        raise TaskValidationError('Политика приёмки неизменяема после публикации.', code=ERROR_CODE)


def atomic_policy_write(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        using=kwargs.get('using') or getattr(self, 'db', None) or getattr(getattr(self, '_state', None), 'db', None) or 'default'
        try:
            with transaction.atomic(using=using):
                return method(self, *args, **kwargs)
        except IntegrityError as exc:
            if ERROR_CODE not in str(exc): raise
            raise TaskValidationError('Политика приёмки неизменяема после публикации.', code=ERROR_CODE) from exc
    return wrapped
