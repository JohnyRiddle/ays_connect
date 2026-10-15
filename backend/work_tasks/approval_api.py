from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from employees.models import Employee
from access_control.services import PermissionService
from .models import TaskApproval, TaskComment
from .approvals import ApprovalService, require, visible_source, can_invite_approver
from .approval_serializers import ApprovalSerializer, ApprovalRequestSerializer, ApprovalCommandSerializer, ApprovalCandidateSerializer, ApprovalErrorSerializer
from .routing import eligible_for_location


TASK_PARAMS=[OpenApiParameter('id',OpenApiTypes.UUID,OpenApiParameter.PATH)]
APPROVAL_PARAMS=TASK_PARAMS+[OpenApiParameter('approval_id',OpenApiTypes.UUID,OpenApiParameter.PATH)]
COMMENT_PARAMS=TASK_PARAMS+[OpenApiParameter('comment_id',OpenApiTypes.UUID,OpenApiParameter.PATH)]
ERRORS={400:ApprovalErrorSerializer,401:ApprovalErrorSerializer,403:ApprovalErrorSerializer,404:ApprovalErrorSerializer,409:ApprovalErrorSerializer}


class ApprovalActionsMixin:
    def _approvals(self,task):
        user=self.request.user;actor=self._actor()
        if not actor or not eligible_for_location(actor,task.location) or not (user.is_superuser or PermissionService.has_permission(employee=actor,permission='task.approval.view',obj=task)):
            raise PermissionDenied('Нет права просматривать согласования.')
        qs=TaskApproval.objects.filter(task=task).select_related('task','comment','requester','approver').prefetch_related('history__actor')
        if not (user.is_superuser or PermissionService.has_permission(employee=actor,permission='task.comment_internal',obj=task)):
            qs=qs.filter(source_internal=False,comment__is_internal=False)
        return qs

    @extend_schema(request=ApprovalRequestSerializer,responses={201:ApprovalSerializer,**ERRORS},description='Explicit approval request for one eligible employee. Creates approval participation without a watcher. Does not mutate any Task fields. command_id makes retries idempotent.',tags=['Task comment approvals'],parameters=TASK_PARAMS,methods=['POST'])
    @extend_schema(responses={200:ApprovalSerializer(many=True),**ERRORS},tags=['Task comment approvals'],parameters=TASK_PARAMS,methods=['GET'])
    @action(detail=True,methods=['get','post'],url_path='approvals')
    def approvals(self,request,pk=None):
        task=self.get_object();qs=self._approvals(task)
        if request.method=='GET':return Response(ApprovalSerializer(qs,many=True,context={'request':request}).data)
        data=ApprovalRequestSerializer(data=request.data);data.is_valid(raise_exception=True);v=data.validated_data
        comment=get_object_or_404(TaskComment,pk=v['comment'],task=task)
        approver=get_object_or_404(Employee.objects.select_related('user'),pk=v['approver'])
        result=ApprovalService.request(comment=comment,approver=approver,actor=self._actor(),user=request.user,text=v['text'],command_id=v['command_id'],correlation_id=self._correlation_id())
        return Response(ApprovalSerializer(result,context={'request':request}).data,status=201)

    @extend_schema(responses={200:ApprovalCandidateSerializer(many=True),**ERRORS},tags=['Task comment approvals'],parameters=COMMENT_PARAMS,description='Eligible approvers with object scope and prospective participating permissions. Selection alone grants no access; submitting an approval makes its approver a task participant.')
    @action(detail=True,methods=['get'],url_path=r'comments/(?P<comment_id>[^/.]+)/approval-options')
    def approval_options(self,request,pk=None,comment_id=None):
        task=self.get_object();self._approvals(task)
        comment=get_object_or_404(TaskComment,pk=comment_id,task=task,deleted_at__isnull=True,author=self._actor())
        require(employee=self._actor(),user=request.user,permission='task.approval.request',task=task,comment=comment)
        result=[]
        from employees.assignment_targets import assignment_visibility
        for employee in assignment_visibility(request.user)[0].select_related('user').order_by('last_name','first_name','pk'):
            if employee.pk==self._actor().pk:continue
            if can_invite_approver(employee=employee,task=task,comment=comment):
                result.append({'id':str(employee.pk),'name':employee.display_name})
        return Response(result)

    @extend_schema(responses={200:ApprovalSerializer,**ERRORS},tags=['Task comment approvals'],parameters=APPROVAL_PARAMS,description='Read-only approval with immutable event history. No generic update or delete is exposed.')
    @action(detail=True,methods=['get'],url_path=r'approvals/(?P<approval_id>[^/.]+)')
    def approval_detail(self,request,pk=None,approval_id=None):
        obj=get_object_or_404(self._approvals(self.get_object()),pk=approval_id)
        return Response(ApprovalSerializer(obj,context={'request':request}).data)

    def _approval_command(self,request,pk,approval_id,command):
        task=self.get_object();obj=get_object_or_404(self._approvals(task),pk=approval_id)
        data=ApprovalCommandSerializer(data=request.data);data.is_valid(raise_exception=True)
        result=ApprovalService.command(approval=obj,actor=self._actor(),user=request.user,action=command,correlation_id=self._correlation_id(),**data.validated_data)
        return Response(ApprovalSerializer(result,context={'request':request}).data)

    @extend_schema(request=ApprovalCommandSerializer,responses={200:ApprovalSerializer,**ERRORS},tags=['Task comment approvals'],parameters=APPROVAL_PARAMS,description='Assigned approver confirms with mandatory text. Task lifecycle is unchanged.')
    @action(detail=True,methods=['post'],url_path=r'approvals/(?P<approval_id>[^/.]+)/approve')
    def approval_approve(self,request,pk=None,approval_id=None):return self._approval_command(request,pk,approval_id,'approve')

    @extend_schema(request=ApprovalCommandSerializer,responses={200:ApprovalSerializer,**ERRORS},tags=['Task comment approvals'],parameters=APPROVAL_PARAMS,description='Assigned approver requests clarification with mandatory text.')
    @action(detail=True,methods=['post'],url_path=r'approvals/(?P<approval_id>[^/.]+)/clarify')
    def approval_clarify(self,request,pk=None,approval_id=None):return self._approval_command(request,pk,approval_id,'clarify')

    @extend_schema(request=ApprovalCommandSerializer,responses={200:ApprovalSerializer,**ERRORS},tags=['Task comment approvals'],parameters=APPROVAL_PARAMS,description='Requester starts another numbered round after clarification or approval; previous history remains immutable.')
    @action(detail=True,methods=['post'],url_path=r'approvals/(?P<approval_id>[^/.]+)/resubmit')
    def approval_resubmit(self,request,pk=None,approval_id=None):return self._approval_command(request,pk,approval_id,'resubmit')

    @extend_schema(request=ApprovalCommandSerializer,responses={200:ApprovalSerializer,**ERRORS},tags=['Task comment approvals'],parameters=APPROVAL_PARAMS,description='Requester or authorized administrator cancels a pending/clarification approval with a reason. Task is not cancelled.')
    @action(detail=True,methods=['post'],url_path=r'approvals/(?P<approval_id>[^/.]+)/cancel')
    def approval_cancel(self,request,pk=None,approval_id=None):return self._approval_command(request,pk,approval_id,'cancel')
