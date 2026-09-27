"""Synthetic, scoped personas for LOCAL STAGING only. Never print credentials."""
import json
import os
from pathlib import Path
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import User
from access_control.models import EmployeeRole, Permission, Role, RolePermission
from organizations.models import LegalEntity, OrgUnit
from employees.models import AssignmentTarget, Employee, Position, Team, TeamMembership
from employees.services import EmployeeService, EmployeeAssignmentService, EmployeeManagerService
from employees.onboarding_lifecycle import OnboardingTemplateService
from work_tasks.models import TaskTemplate


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--run', required=True)

    def handle(self, *args, **options):
        run = options['run']
        if (os.environ.get('PEOPLE_ACCEPTANCE_MODE') != '1'
            or settings.DATABASES['default']['HOST'] != 'db'
            or settings.DATABASES['default']['NAME'] != 'people_acceptance'):
            raise CommandError('Only the explicitly isolated local acceptance database is allowed.')
        if not re.fullmatch(r'[a-z0-9]{1,12}', run):
            raise CommandError('Use a short alphanumeric run ID.')
        path = Path('/staging-private') / f'{run}.json'
        if path.exists():
            data = json.loads(path.read_text())
            self.stdout.write(json.dumps({'run': run, 'reused': True, 'employee_ids': {k:v['employee'] for k,v in data['actors'].items()}}))
            return
        prefix = f'pa-{run}'
        if Role.objects.filter(code__startswith=prefix).exists():
            raise CommandError('Run exists without its private manifest; refusing to alter existing rows.')
        data = {'run': run, 'actors': {}}
        self_codes = ['people.onboarding.view_self', 'people.onboarding.step_complete_self',
                      'people.change_request.create_self', 'people.change_request.view_self',
                      'task.view', 'task.start', 'task.complete', 'task.accept', 'task.comment']
        hr_codes = ['people.employee.view', 'people.employee.manage', 'people.assignment.view',
                    'people.assignment.manage', 'people.manager.view', 'people.manager.manage',
                    'people.invitation.view', 'people.invitation.create', 'people.invitation.resend',
                    'people.invitation.revoke', 'people.change_request.review', 'people.change_request.apply',
                    'people.change_request.manage', 'people.onboarding.view', 'people.onboarding.assign',
                    'people.onboarding.manage', 'people.onboarding.step_skip',
                    'people.account_access.suspend', 'people.account_access.restore',
                    'people.account_access.view', 'people.account_access.reactivate',
                    'people.directory.view', 'task.create', 'task.view', 'task.assign', 'task.accept',
                    'task.reject', 'task.cancel', 'task.reopen', 'task_template.use']
        with transaction.atomic():
            entity = LegalEntity.objects.create(name=prefix, code=prefix)
            units = [OrgUnit.objects.create(name=f'{prefix}-{n}', code=f'{prefix}-{n}', legal_entity=entity) for n in ('a','b')]
            positions = [Position.objects.create(name=f'{prefix}-position-{n}', code=f'{prefix}-position-{n}', org_unit=u, legal_entity=entity) for n,u in enumerate(units)]
            for name in ('setup','hr','manager','employee','teammate','outside','outsidehr','coordinator'):
                unit = units[1] if name in {'outside','outsidehr'} else units[0]
                password = secrets.token_urlsafe(32)
                email = f'{prefix}-{name}@example.test'
                user = None if name == 'employee' else User.objects.create_user(username=email, email=email, password=password, first_name=name, last_name='Synthetic')
                employee = EmployeeService.create(user=user, first_name=name, last_name='Synthetic', work_email=email)
                EmployeeAssignmentService.start(employee=employee, actor_user=user, is_primary=True,
                    org_unit=unit, legal_entity=entity, position=positions[units.index(unit)])
                role = Role.objects.create(code=f'{prefix}-{name}', name=f'Synthetic {name}')
                for code in self_codes:
                    RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code), scope='own')
                directory_scope = 'org_unit' if name in {'hr','manager','outsidehr','coordinator','setup'} else 'team'
                RolePermission.objects.create(role=role, permission=Permission.objects.get(code='people.directory.view'), scope=directory_scope)
                if name in {'hr','outsidehr','coordinator','setup'}:
                    for code in hr_codes:
                        RolePermission.objects.get_or_create(role=role, permission=Permission.objects.get(code=code), scope='org_unit')
                if name in {'hr','outsidehr'}:
                    RolePermission.objects.create(role=role,permission=Permission.objects.get(code='people.profile.view_sensitive'),scope='org_unit')
                EmployeeRole.objects.create(employee=employee, role=role, org_unit=unit)
                data['actors'][name] = {'employee':str(employee.pk), 'user':user.pk if user else None, 'email':email, 'password':password}
            manager = Employee.objects.get(pk=data['actors']['manager']['employee'])
            for name in ('employee','teammate'):
                EmployeeManagerService.change(employee=Employee.objects.get(pk=data['actors'][name]['employee']), manager=manager)
            teams = [Team.objects.create(code=f'{prefix}-team-{n}', name=f'{prefix}-team-{n}', org_unit=u, legal_entity=entity, status='active') for n,u in enumerate(units)]
            for name in ('employee','teammate','manager','outside'):
                TeamMembership.objects.create(employee_id=data['actors'][name]['employee'], team=teams[1 if name=='outside' else 0])
            invited = Employee.objects.get(pk=data['actors']['employee']['employee'])
            coordinator = Employee.objects.get(pk=data['actors']['coordinator']['employee'])
            target = AssignmentTarget.objects.create(target_type='employee', employee=invited)
            task = TaskTemplate.objects.create(name=prefix, task_title=f'{prefix} Work acceptance',
                responsible_target=target, executor_target=target, acceptance_policy='responsible', created_by=coordinator,
                org_unit=units[0], legal_entity=entity)
            template = OnboardingTemplateService.create(actor_user=coordinator.user, name=prefix, scope='org_unit', org_unit=units[0])
            OnboardingTemplateService.publish(template=template, actor_user=coordinator.user, expected_version=1, steps=[
                {'key':'profile','title':'Профиль сотрудника','step_type':'profile','responsible_strategy':'self'},
                {'key':'manual','title':'Первый рабочий шаг','step_type':'manual','responsible_strategy':'self','dependencies':['profile']},
                {'key':'work','title':'Рабочая задача','step_type':'task','task_template':task,'responsible_strategy':'self','dependencies':['manual'],'due_offset':timedelta(seconds=5)},
                {'key':'optional','title':'Необязательный шаг','step_type':'manual','required':False,'responsible_strategy':'self'},
            ])
            data.update(template=str(template.pk), task_template=str(task.pk), units=[str(x.pk) for x in units], teams=[str(x.pk) for x in teams])
            # A private manifest is a test harness output, never an application/public artifact.
            with path.open('x') as stream:
                json.dump(data, stream)
            path.chmod(0o600)
        self.stdout.write(json.dumps({'run':run, 'reused':False, 'employee_ids':{k:v['employee'] for k,v in data['actors'].items()}}))
