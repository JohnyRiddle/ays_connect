import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.utils import timezone
from django.test import TestCase,TransactionTestCase,override_settings
from django.db import transaction,connection,connections,DatabaseError
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied
from accounts.models import User
from employees.models import Employee,Position,AssignmentTarget
from organizations.models import OrgUnit,Location
from access_control.models import Role,Permission,RolePermission,EmployeeRole
from audit.models import AuditEvent
from events.models import OutboxEvent
from notifications.models import Notification,NotificationDelivery,TelegramAccount
from notifications.task_events import ingest_task_event
from notifications.bot_api import allowed_delivery
from .models import Task,TaskComment,TaskApproval,TaskApprovalEvent,ApprovalStatus,TaskDeadlineHistory,TaskStatusHistory
from .services import TaskService
from .collaboration import CollaborationService
from .approvals import ApprovalService,actions
from .exceptions import TaskValidationError,TaskVersionConflict


class ApprovalFixture:
    def setUp(self):
        self.user=User.objects.create_superuser(username='approval-author',email='author@approval.invalid')
        self.unit=OrgUnit.objects.create(name='Approval staging IT')
        position=Position.objects.create(name='Head',org_unit=self.unit)
        self.actor=Employee.objects.create(user=self.user,first_name='Автор',org_unit=self.unit,position_ref=position)
        self.unit.manager_position=position;self.unit.save()
        self.approver_user=User.objects.create_user(username='approval-person',email='person@approval.invalid')
        self.approver=Employee.objects.create(user=self.approver_user,first_name='Согласующий',org_unit=self.unit)
        target=AssignmentTarget.objects.create(target_type='employee',employee=self.approver)
        self.task=TaskService.create(actor=self.actor,actor_user=self.user,title='Synthetic approval',responsible_department=self.unit,executor_target=target)
        self.role=Role.objects.create(code='approval-test',name='Approval synthetic')
        for code in ['task.view','task.comment','task.approval.view','task.approval.request','task.approval.respond','task.approval.cancel']:
            permission,_=Permission.objects.get_or_create(code=code,defaults={'name':code})
            RolePermission.objects.create(role=self.role,permission=permission,scope='participating')
        EmployeeRole.objects.create(role=self.role,employee=self.approver)
        self.comment=CollaborationService.add_comment(task=self.task,actor=self.actor,actor_user=self.user,body='@Согласующий проверьте предложение',mentions=[self.approver])
        self.api=APIClient();self.api.force_authenticate(self.user)
        self.url=f'/api/internal/v1/tasks/{self.task.pk}/approvals/'

    def request(self,**kwargs):
        return ApprovalService.request(comment=self.comment,approver=self.approver,actor=self.actor,user=self.user,text='Прошу согласовать',command_id=uuid.uuid4(),**kwargs)

    def command(self,a,action='approve',actor=None,user=None,version=None,command_id=None,text='Подтверждаю'):
        actor=actor or (self.actor if action in ['cancel','resubmit'] else self.approver)
        user=user or (self.user if actor==self.actor else self.approver_user)
        return ApprovalService.command(approval=a,actor=actor,user=user,action=action,text=text,version=version or a.version,command_id=command_id or uuid.uuid4())

    def snapshot(self):
        return Task.objects.filter(pk=self.task.pk).values().get(),list(TaskStatusHistory.objects.filter(task=self.task).values()),list(TaskDeadlineHistory.objects.filter(task=self.task).values())


class ApprovalTests(ApprovalFixture,TestCase):
    def test_plain_mention_does_not_request_approval(self):
        self.assertFalse(TaskApproval.objects.exists())
        self.assertFalse(OutboxEvent.objects.filter(event_type__startswith='task.approval.').exists())

    def test_all_rounds_leave_every_task_column_and_histories_identical(self):
        before=self.snapshot()
        with patch.object(Task,'save',side_effect=AssertionError('Task.save forbidden')):
            a=self.request();self.assertEqual(a.status,'PENDING')
            a=self.command(a,'clarify',text='Уточните сумму');self.assertEqual(a.status,'CLARIFICATION_REQUESTED')
            a=self.command(a,'resubmit',text='Уточнённая сумма');self.assertEqual(a.round_number,2)
            a=self.command(a);self.assertEqual(a.status,'APPROVED')
            a=self.command(a,'resubmit',text='Новый вариант');self.assertEqual(a.round_number,3)
            a=self.command(a,'cancel',text='Больше не требуется');self.assertEqual(a.status,'CANCELLED')
        self.assertEqual(before,self.snapshot())
        self.assertEqual(list(a.history.values_list('sequence',flat=True)),[1,2,3,4,5,6])
        self.assertEqual(list(a.history.values_list('round_number',flat=True)),[1,1,2,2,3,3])
        self.assertEqual(AuditEvent.objects.filter(entity_type='TaskApproval').count(),6)
        self.assertEqual(OutboxEvent.objects.filter(event_type__startswith='task.approval.').count(),6)

    def test_independent_of_all_task_statuses(self):
        from .models import TaskStatus
        for status in TaskStatus.values:
            Task.objects.filter(pk=self.task.pk).update(status=status,completed_at=timezone.now() if status=='completed' else None,cancelled_at=timezone.now() if status=='cancelled' else None)
            comment=CollaborationService.add_comment(task=self.task,actor=self.actor,actor_user=self.user,body='Новый запрос',mentions=[self.approver])
            before=self.snapshot()
            a=ApprovalService.request(comment=comment,approver=self.approver,actor=self.actor,user=self.user,text='Запрос',command_id=uuid.uuid4())
            self.command(a)
            self.assertEqual(before,self.snapshot())

    def test_only_mentioned_active_visible_approver_with_permission(self):
        self.comment.mention_records.all().delete()
        with self.assertRaises(TaskValidationError):self.request()
        self.assertFalse(TaskApproval.objects.exists())

    def test_self_request_is_rejected(self):
        from .models import TaskCommentMention
        TaskCommentMention.objects.create(comment=self.comment,employee=self.actor)
        with self.assertRaises(TaskValidationError):ApprovalService.request(comment=self.comment,approver=self.actor,actor=self.actor,user=self.user,text='Сам',command_id=uuid.uuid4())

    def test_no_automatic_scope_grants_for_unavailable_approver(self):
        self.approver.is_active=False;self.approver.save()
        count=EmployeeRole.objects.count()
        with self.assertRaises(TaskValidationError):self.request()
        self.assertEqual(count,EmployeeRole.objects.count())

    def test_object_scope_and_internal_comments_are_enforced(self):
        self.comment.is_internal=True;self.comment.save()
        with self.assertRaises(TaskValidationError):self.request()
        p,_=Permission.objects.get_or_create(code='task.comment_internal',defaults={'name':'Internal'})
        RolePermission.objects.create(role=self.role,permission=p,scope='participating')
        a=self.request()
        obj=Location.objects.create(name='Denied object')
        Task.objects.filter(pk=self.task.pk).update(location=obj)
        with self.assertRaises(PermissionDenied):self.command(a)

    def test_superuser_cannot_decide_instead_of_designated_employee(self):
        a=self.request()
        with self.assertRaises(PermissionDenied):self.command(a,actor=self.actor,user=self.user)
        self.assertEqual(a.history.count(),1)

    def test_request_only_by_original_author(self):
        with self.assertRaises(PermissionDenied):ApprovalService.request(comment=self.comment,approver=self.actor,actor=self.approver,user=self.approver_user,text='Запрос',command_id=uuid.uuid4())

    def test_request_and_command_retry_are_idempotent(self):
        key=uuid.uuid4();a=ApprovalService.request(comment=self.comment,approver=self.approver,actor=self.actor,user=self.user,text='Запрос',command_id=key)
        b=ApprovalService.request(comment=self.comment,approver=self.approver,actor=self.actor,user=self.user,text='Запрос',command_id=key)
        self.assertEqual(a.pk,b.pk)
        key=uuid.uuid4();self.command(a,command_id=key);self.command(a,version=1,command_id=key)
        self.assertEqual(a.history.count(),2)
        with self.assertRaises(TaskVersionConflict):self.command(a,text='Другой текст',command_id=key)

    def test_duplicate_approver_request_is_conflict(self):
        self.request()
        with self.assertRaises(TaskVersionConflict):self.request()

    def test_stale_version_conflict_has_no_partial_writes(self):
        a=self.request();b=self.command(a,'clarify');b=self.command(b,'resubmit')
        count=OutboxEvent.objects.count()
        with self.assertRaises(TaskVersionConflict):self.command(b,version=1)
        self.assertEqual(count,OutboxEvent.objects.count())
        self.assertEqual(b.history.count(),3)

    def test_blank_text_rejected_everywhere_and_cancel_terminal(self):
        a=self.request()
        for action in ['approve','clarify','cancel']:
            with self.assertRaises(TaskValidationError):self.command(a,action,text='  ')
        a=self.command(a,'cancel')
        with self.assertRaises(PermissionDenied):self.command(a,'resubmit')
        self.assertEqual(a.history.count(),2)

    def test_revoked_respond_permission_blocks_decision(self):
        a=self.request();RolePermission.objects.filter(role=self.role,permission__code='task.approval.respond').delete()
        with self.assertRaises(PermissionDenied):self.command(a)
        self.assertEqual(actions(a,self.approver,self.approver_user),[])

    def test_transaction_rolls_back_state_history_and_audit_if_outbox_fails(self):
        a=self.request();audit=AuditEvent.objects.count()
        with patch('work_tasks.approvals.DomainEventService.publish',side_effect=RuntimeError('outbox failed')):
            with self.assertRaises(RuntimeError):self.command(a)
        a.refresh_from_db();self.assertEqual(a.status,'PENDING');self.assertEqual(a.history.count(),1);self.assertEqual(audit,AuditEvent.objects.count())

    def test_snapshot_and_history_survive_comment_edit_delete(self):
        a=self.request();body=a.source_body
        CollaborationService.edit_comment(comment=self.comment,actor=self.actor,actor_user=self.user,body='Изменён',mentions=[])
        CollaborationService.delete_comment(comment=self.comment,actor=self.actor,actor_user=self.user)
        a=self.command(a);self.assertEqual(a.source_body,body);self.assertEqual(a.history.first().text,'Прошу согласовать')

    def test_api_contract_mandatory_text_cross_task_scope_and_read_only_history(self):
        r=self.api.post(self.url,{'comment':str(self.comment.pk),'approver':str(self.approver.pk),'text':'Запрос','command_id':str(uuid.uuid4())},format='json')
        self.assertEqual(r.status_code,201);aid=r.data['id'];self.assertEqual(r.data['status'],'PENDING')
        self.api.force_authenticate(self.approver_user)
        self.assertEqual(self.api.get(self.url).status_code,200)
        self.assertEqual(self.api.post(self.url+aid+'/approve/',{'text':' ','version':1,'command_id':str(uuid.uuid4())},format='json').status_code,400)
        r=self.api.post(self.url+aid+'/approve/',{'text':'Да','version':1,'command_id':str(uuid.uuid4())},format='json');self.assertEqual(r.status_code,200)
        self.assertEqual(self.api.patch(self.url+aid+'/',{'status':'PENDING'},format='json').status_code,405)
        self.assertEqual(self.api.get('/api/internal/v1/tasks/'+str(uuid.uuid4())+'/approvals/').status_code,404)

    def test_api_view_without_new_permission_and_internal_history_denied(self):
        a=self.request();self.api.force_authenticate(self.approver_user)
        RolePermission.objects.filter(role=self.role,permission__code='task.approval.view').delete()
        self.assertEqual(self.api.get(self.url).status_code,403)
        self.assertEqual(self.api.post(self.url+str(a.pk)+'/approve/',{'text':'Да','version':1,'command_id':str(uuid.uuid4())},format='json').status_code,403)

    @override_settings(NOTIFICATIONS_TELEGRAM_ENABLED=True,NOTIFICATIONS_EMAIL_ENABLED=False)
    def test_notification_engine_idempotency_safe_content_and_revoke_before_delivery(self):
        TelegramAccount.objects.create(employee=self.approver,telegram_chat_id='123456',telegram_user_id='123456',linked_at=timezone.now())
        a=self.request();event=OutboxEvent.objects.get(event_type='task.approval.request')
        intent=ingest_task_event(event);ingest_task_event(event)
        notification=Notification.objects.get(intent=intent,recipient_employee=self.approver)
        self.assertEqual(Notification.objects.filter(intent=intent).count(),1)
        self.assertNotIn(self.comment.body,json_dump(intent.payload));self.assertNotIn('Прошу согласовать',notification.message)
        delivery=NotificationDelivery.objects.get(notification=notification,channel='telegram');self.assertEqual(delivery.status,'pending');self.assertEqual(allowed_delivery(delivery),'')
        RolePermission.objects.filter(role=self.role,permission__code='task.approval.view').delete()
        self.assertEqual(allowed_delivery(delivery),'APPROVAL_ACCESS_REVOKED')

    def test_postgresql_history_and_identity_cannot_be_changed_through_bulk_or_sql(self):
        a=self.request();e=a.history.get()
        for operation in [lambda:TaskApprovalEvent.objects.filter(pk=e.pk).update(text='tamper'),lambda:TaskApprovalEvent.objects.filter(pk=e.pk).delete(),lambda:TaskApproval.objects.filter(pk=a.pk).update(source_body='tamper')]:
            with self.assertRaises(DatabaseError):
                with transaction.atomic():operation()
        with self.assertRaises(ValueError):e.delete()
        e.text='tamper'
        with self.assertRaises(ValueError):e.save()


def json_dump(value):
    import json
    return json.dumps(value,ensure_ascii=False)


class ApprovalConcurrencyTests(ApprovalFixture,TransactionTestCase):
    def test_concurrent_decisions_only_one_history_event_and_task_untouched(self):
        a=self.request();before=self.snapshot()
        def decide(action):
            connections.close_all()
            try:
                ApprovalService.command(approval=a,actor=self.approver,user=self.approver_user,action=action,text='Concurrent decision',version=1,command_id=uuid.uuid4())
                return 'ok'
            except (TaskVersionConflict,PermissionDenied):return 'conflict'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(decide,['approve','clarify']))
        self.assertEqual(sorted(result),['conflict','ok']);self.assertEqual(a.history.count(),2);self.assertEqual(before,self.snapshot())

    def test_deferred_guard_rejects_unlogged_transition(self):
        a=self.request()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():TaskApproval.objects.filter(pk=a.pk).update(status='APPROVED',version=2)
        a.refresh_from_db();self.assertEqual(a.status,'PENDING')
