import os,json
from django.db import transaction
from accounts.models import User
from employees.models import Employee,Position,AssignmentTarget
from organizations.models import OrgUnit
from access_control.models import Role,Permission,RolePermission,EmployeeRole
from work_tasks.services import TaskService
from work_tasks.collaboration import CollaborationService
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
@transaction.atomic
def seed():
 assert not User.objects.exists(),'staging DB must start empty'
 role=Role.objects.create(code='approval-staging-participant',name='Участник согласования (staging)')
 for code in ['task.view','task.create','task.assign','task.start','task.comment','task.approval.view','task.approval.request','task.approval.respond','task.approval.cancel','task.checklist_manage','task.checklist_complete']:
  permission,_=Permission.objects.get_or_create(code=code,defaults={'name':code});RolePermission.objects.create(role=role,permission=permission,scope='participating')
 unit=OrgUnit.objects.create(name='IT (учебный staging)');position=Position.objects.create(name='Руководитель',org_unit=unit)
 people=[]
 for key,first,last in [('requester','Анна','Инициатор'),('approver','Сергей','Согласующий')]:
  user=User.objects.create_user(username=key,email=key+'@approvals.demo.invalid',password='Demo12345!',first_name=first,last_name=last)
  employee=Employee.objects.create(user=user,first_name=first,last_name=last,org_unit=unit,position_ref=position if key=='requester' else None)
  EmployeeRole.objects.create(employee=employee,role=role);people.append((user,employee))
 viewer=Role.objects.create(code='approval-staging-directory',name='Учебный справочник')
 for code in ['employee.view','org_unit.view']:
  permission,_=Permission.objects.get_or_create(code=code,defaults={'name':code});RolePermission.objects.create(role=viewer,permission=permission,scope='global')
 for user,employee in people:EmployeeRole.objects.create(employee=employee,role=viewer)
 unit.manager_position=position;unit.save()
 user,actor=people[0];apuser,approver=people[1]
 target=AssignmentTarget.objects.create(target_type='employee',employee=approver)
 task=TaskService.create(actor=actor,actor_user=user,title='STAGING: согласование предложения в чате',description='Учебный пример. Согласование обсуждения не меняет состояние задачи.',responsible_department=unit,executor_target=target)
 task=TaskService.publish(task=task,actor=actor,actor_user=user,version=task.version)
 task=TaskService.start(task=task,actor=approver,actor_user=apuser,version=task.version)
 comment=CollaborationService.add_comment(task=task,actor=actor,actor_user=user,body='@Согласующий Сергей прошу проверить предложение по закупке.',mentions=[approver])
 data={'task':str(task.pk),'comment':str(comment.pk),'approver':str(approver.pk),'requester':str(actor.pk)}
 return data


class Command(BaseCommand):
    help='Create synthetic, local-only comment approval staging fixture; never production.'
    def add_arguments(self,parser):
        parser.add_argument('--fixture-output',required=True)
    def handle(self,*args,**options):
        db=settings.DATABASES['default']
        if os.getenv('AYS_APPROVAL_STAGING')!='1' or not settings.DEBUG or db.get('HOST') not in ['127.0.0.1','localhost'] or not str(db['NAME']).startswith('ays_approval_staging') or settings.NOTIFICATIONS_TELEGRAM_ENABLED or settings.NOTIFICATIONS_EMAIL_ENABLED:
            raise CommandError('Requires explicit local approval staging DB, DEBUG and disabled external channels.')
        if User.objects.exists():raise CommandError('Use a fresh empty synthetic staging database; existing users will not be replaced.')
        result=seed()
        Path(options['fixture_output']).write_text(json.dumps(result),encoding='utf-8')
        self.stdout.write(json.dumps(result))
