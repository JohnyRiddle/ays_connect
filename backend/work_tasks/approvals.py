"""Comment approval commands deliberately never call TaskService or save a Task."""
from functools import wraps
from django.db import transaction, IntegrityError
from rest_framework.exceptions import PermissionDenied
from access_control.services import PermissionService
from audit.services import AuditService
from events.services import DomainEventService
from employees.assignment_targets import assignable_employees
from .models import Task, TaskApproval, TaskApprovalEvent, TaskComment, ApprovalStatus
from .selectors import TaskSelector
from .routing import eligible_for_location
from .exceptions import TaskValidationError, TaskVersionConflict


def atomic_approval(method):
    @wraps(method)
    def wrapped(*args,**kwargs):
        try:
            with transaction.atomic():return method(*args,**kwargs)
        except IntegrityError as exc:
            if 'command_id' in str(exc) or 'task_approval_comment_approver_unique' in str(exc):
                raise TaskVersionConflict('Команда или согласование уже существует.',code='approval_command_conflict') from exc
            raise
    return wrapped


def visible_source(*, employee, user, task, comment, approval=None):
    if not employee or not user or not user.is_active or employee.user_id != user.pk:
        return False
    if not assignable_employees().filter(pk=employee.pk).exists():
        return False
    if not TaskSelector.visible_to(employee).filter(pk=task.pk).exists() or not eligible_for_location(employee, task.location):
        return False
    internal = comment.is_internal or bool(approval and approval.source_internal)
    return not internal or user.is_superuser or PermissionService.has_permission(employee=employee, permission='task.comment_internal', obj=task)


def can_invite_approver(*, employee, task, comment):
    """Validate prospective participation without granting a role or a watcher."""
    from .policies import TaskAccessPolicy
    if not employee or not employee.user_id or not employee.user.is_active:
        return False
    if not assignable_employees().filter(pk=employee.pk).exists() or not eligible_for_location(employee, task.location):
        return False
    def allowed(code):
        return employee.user.is_superuser or TaskAccessPolicy.allows(
            employee=employee, permission=code, task=task, approval_invitation=True)
    if not all(allowed(code) for code in ['task.view', 'task.approval.view', 'task.approval.respond']):
        return False
    # Internal comments require an existing explicit internal-comment grant.
    return not comment.is_internal or employee.user.is_superuser or PermissionService.has_permission(
        employee=employee, permission='task.comment_internal', obj=task)


def require(*, employee, user, permission, task, comment, approval=None):
    if not visible_source(employee=employee, user=user, task=task, comment=comment, approval=approval):
        raise PermissionDenied('Нет доступа к согласованию.')
    if not user.is_superuser and (not PermissionService.has_permission(employee=employee, permission='task.approval.view', obj=task) or not PermissionService.has_permission(employee=employee, permission=permission, obj=task)):
        raise PermissionDenied('Нет права на действие согласования.')


def actions(approval, employee, user):
    result=[]
    if not visible_source(employee=employee,user=user,task=approval.task,comment=approval.comment,approval=approval):
        return result
    def allowed(code):
        return user.is_superuser or (PermissionService.has_permission(employee=employee,permission='task.approval.view',obj=approval.task) and PermissionService.has_permission(employee=employee,permission='task.approval.'+code,obj=approval.task))
    if employee.pk == approval.approver_id and approval.status == ApprovalStatus.PENDING and allowed('respond'):
        result += ['approve','clarify']
    if employee.pk == approval.requester_id and approval.status in [ApprovalStatus.CLARIFICATION_REQUESTED, ApprovalStatus.APPROVED] and allowed('request'):
        result += ['resubmit']
    if (employee.pk == approval.requester_id or user.is_superuser) and approval.status in [ApprovalStatus.PENDING,ApprovalStatus.CLARIFICATION_REQUESTED] and allowed('cancel'):
        result += ['cancel']
    return result


class ApprovalService:
    @staticmethod
    def _text(text):
        value=text.strip()
        if not value or len(value)>10000:
            raise TaskValidationError('Укажите текст от 1 до 10000 символов.',code='approval_text_required')
        return value

    @staticmethod
    def _replay(command_id, *, actor, action, text, approval=None, comment=None, approver=None):
        event=TaskApprovalEvent.objects.select_related('approval').filter(command_id=command_id).first()
        if not event:
            return None
        a=event.approval
        if event.actor_id!=actor.pk or event.action!=action or event.text!=text or (approval and a.pk!=approval.pk) or (comment and (a.comment_id!=comment.pk or a.approver_id!=approver.pk)):
            raise TaskVersionConflict('command_id уже использован для другого действия.',code='approval_command_conflict')
        return a

    @staticmethod
    def _record(approval, *, actor, user, action, text, command_id, old_status, correlation_id):
        event=TaskApprovalEvent.objects.create(approval=approval,command_id=command_id,sequence=approval.version,round_number=approval.round_number,actor=actor,action=action,from_status=old_status,to_status=approval.status,text=text)
        payload={'task_id':str(approval.task_id),'approval_id':str(approval.pk),'approval_event_id':str(event.pk),'comment_id':str(approval.comment_id),'actor_id':str(actor.pk),'requester_id':str(approval.requester_id),'approver_id':str(approval.approver_id),'round_number':approval.round_number,'status':approval.status,'is_internal':approval.source_internal or approval.comment.is_internal}
        # No comment/request/decision body in audit metadata or notification payloads.
        AuditService.record(action='task.approval.'+action,entity=approval,actor_user=user,actor_employee=actor,metadata=payload,correlation_id=correlation_id)
        DomainEventService.publish(event_type='task.approval.'+action,entity=approval,actor=user,payload=payload,correlation_id=correlation_id)
        return approval

    @classmethod
    @atomic_approval
    def request_from_task(cls, *, task, approver, actor, user, text, command_id, correlation_id=None):
        from .collaboration import CollaborationService
        # Serialize retries on this task without saving or changing any Task field.
        task=Task.objects.select_for_update(no_key=True).get(pk=task.pk)
        source=TaskComment(task=task,author=actor,body='',is_internal=False)
        require(employee=actor,user=user,permission='task.approval.request',task=task,comment=source)
        CollaborationService._authorize(actor=actor,actor_user=user,permission='task.comment',task=task)
        text=cls._text(text)
        replay=cls._replay(command_id,actor=actor,action='request',text=text)
        if replay:
            if replay.task_id!=task.pk or replay.approver_id!=approver.pk or replay.source_body!=text or replay.source_internal:
                raise TaskVersionConflict('command_id уже использован для другого запроса.',code='approval_command_conflict')
            require(employee=actor,user=user,permission='task.approval.request',task=task,comment=replay.comment,approval=replay)
            return replay
        comment=CollaborationService.add_comment(task=task,actor=actor,actor_user=user,body=text,correlation_id=correlation_id)
        return cls.request(comment=comment,approver=approver,actor=actor,user=user,text=text,command_id=command_id,correlation_id=correlation_id)

    @classmethod
    @atomic_approval
    def request(cls, *, comment, approver, actor, user, text, command_id, correlation_id=None):
        comment=TaskComment.objects.select_for_update().select_related('task').get(pk=comment.pk)
        require(employee=actor,user=user,permission='task.approval.request',task=comment.task,comment=comment)
        text=cls._text(text)
        replay=cls._replay(command_id,actor=actor,action='request',text=text,comment=comment,approver=approver)
        if replay:return replay
        if comment.deleted_at or comment.author_id!=actor.pk:
            raise PermissionDenied('Запросить согласование может автор доступного комментария.')
        if actor.pk==approver.pk:
            raise TaskValidationError('Выберите другого сотрудника.',code='approval_self_request')
        from employees.assignment_targets import assignment_visibility
        if not assignment_visibility(user)[0].filter(pk=approver.pk).exists() or not can_invite_approver(employee=approver,task=comment.task,comment=comment):
            raise TaskValidationError('Согласующему нужны доступ к объекту и права согласования.',code='approval_approver_unavailable')
        if TaskApproval.objects.filter(comment=comment,approver=approver).exists():
            raise TaskVersionConflict('Согласование уже существует. Используйте новый раунд.',code='approval_already_exists')
        approval=TaskApproval.objects.create(task=comment.task,comment=comment,requester=actor,approver=approver,source_body=comment.body,source_internal=comment.is_internal)
        return cls._record(approval,actor=actor,user=user,action='request',text=text,command_id=command_id,old_status='',correlation_id=correlation_id)

    @classmethod
    @atomic_approval
    def command(cls, *, approval, actor, user, action, text, version, command_id, correlation_id=None):
        # Lock order is comment -> approval for requests, decisions and comment moderation.
        TaskComment.objects.select_for_update().get(pk=approval.comment_id)
        approval=TaskApproval.objects.select_for_update().select_related('task','comment').get(pk=approval.pk)
        permission={'approve':'respond','clarify':'respond','resubmit':'request','cancel':'cancel'}.get(action)
        if not permission:raise TaskValidationError('Неизвестное действие.')
        require(employee=actor,user=user,permission='task.approval.'+permission,task=approval.task,comment=approval.comment,approval=approval)
        text=cls._text(text)
        replay=cls._replay(command_id,actor=actor,action=action,text=text,approval=approval)
        if replay:return replay
        if action not in actions(approval,actor,user):
            raise PermissionDenied('Действие недоступно этому сотруднику или в текущем статусе.')
        if approval.version!=version:
            raise TaskVersionConflict('Согласование изменено. Обновите данные.',code='approval_version_conflict')
        old=approval.status
        approval.status={'approve':ApprovalStatus.APPROVED,'clarify':ApprovalStatus.CLARIFICATION_REQUESTED,'resubmit':ApprovalStatus.PENDING,'cancel':ApprovalStatus.CANCELLED}[action]
        if action=='resubmit':approval.round_number+=1
        approval.version+=1
        approval.save(update_fields=['status','round_number','version'])
        return cls._record(approval,actor=actor,user=user,action=action,text=text,command_id=command_id,old_status=old,correlation_id=correlation_id)
