import uuid
import hashlib
import json

from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from employees.models import AssignmentTarget, Employee
from work_tasks.models import SourceType, Task, TaskStatus, TaskTemplate
from work_tasks.selectors import TaskSelector
from work_tasks.serializers import TaskDetailSerializer, TaskSerializer
from audit.models import AuditEvent

from .models import Project, ProjectAttachment, ProjectComment, ProjectCreateRequest, ProjectMember, ProjectMilestone, ProjectStage, ProjectTaskLink, ProjectTaskLinkHistory
from .policies import ProjectAccessPolicy
from .serializers import (LinkSerializer, MemberSerializer, MemberWriteSerializer, MilestoneActionSerializer,
                          MilestoneSerializer, MilestoneWriteSerializer, MilestoneEditSerializer, MoveProjectSerializer, MoveStageSerializer,
                          ProjectAttachmentSerializer, ProjectCommentSerializer, ProjectCommentWriteSerializer,
                          ProjectEditSerializer, ProjectSerializer, ProjectTaskCreateSerializer, StageSerializer, StageWriteSerializer, StageEditSerializer,
                          UnlinkSerializer, VersionSerializer)
from .services import ProjectBusinessError, ProjectService, ProjectTaskService
from .collaboration import ProjectCollaborationService


def business_call(callback):
    try:
        return callback()
    except ProjectBusinessError as exc:
        if exc.code == "project_permission_denied" or exc.code == "project_task_forbidden":
            raise PermissionDenied(str(exc)) from exc
        if exc.code in {"project_version_conflict", "task_version_conflict", "project_task_already_linked", "project_request_conflict"}:
            from rest_framework.exceptions import APIException
            class Conflict(APIException):
                status_code = 409
                default_code = exc.code
            raise Conflict(str(exc)) from exc
        raise ValidationError({"code":exc.code, "detail":str(exc)}) from exc


def reject_unknown_fields(payload, serializer):
    allowed={name for name,field in serializer.fields.items() if not field.read_only}
    unexpected=set(payload)-allowed
    if unexpected:
        raise ValidationError({"code":"project_unknown_fields","detail":"Недопустимые поля запроса."})


class ProjectViewSet(viewsets.GenericViewSet):
    serializer_class = ProjectSerializer

    def actor(self):
        return getattr(self.request.user, "employee", None)

    def correlation_id(self):
        raw = self.request.headers.get("X-Correlation-ID")
        try:
            return uuid.UUID(raw) if raw else uuid.uuid4()
        except ValueError as exc:
            raise ValidationError("Некорректный X-Correlation-ID.") from exc

    def create_key(self):
        raw=self.request.headers.get("Idempotency-Key")
        if not raw: raise ValidationError("Укажите Idempotency-Key для создания проекта или задачи.")
        try: return uuid.UUID(raw)
        except ValueError as exc: raise ValidationError("Некорректный Idempotency-Key.") from exc

    @transaction.atomic
    def idempotent_create(self, operation, fingerprint, callback):
        digest=hashlib.sha256(json.dumps(fingerprint,sort_keys=True,default=str).encode()).hexdigest()
        record,_=ProjectCreateRequest.objects.select_for_update().get_or_create(
            actor=self.request.user,key=self.create_key(),operation=operation,defaults={"payload_hash":digest})
        if record.payload_hash!=digest:
            raise ProjectBusinessError("Idempotency-Key уже использован с другими данными.","project_request_conflict")
        if record.project_id or record.task_id:
            return record.project if operation=="project" else record.task,False
        result=callback()
        if operation=="project":record.project=result
        else:record.task=result;record.project_id=fingerprint["project_id"]
        record.save(update_fields=["project","task"])
        return result,True

    def get_queryset(self):
        qs = Project.objects.all() if self.request.user.is_superuser else ProjectAccessPolicy.visible_to(self.actor())
        p = self.request.query_params
        for key in ("status", "org_unit", "location", "manager"):
            if p.get(key):
                value=p[key]
                if key!="status":
                    try: value=uuid.UUID(value)
                    except ValueError as exc: raise ValidationError(f"Некорректный фильтр {key}.") from exc
                qs = qs.filter(**{key:value})
        if p.get("participation"):
            value=p["participation"]
            actor=self.actor()
            if value not in {"mine","member","managing"}: raise ValidationError("Некорректный фильтр участия.")
            if not actor: qs=qs.none()
            elif value=="managing": qs=qs.filter(manager=actor)
            elif value=="member": qs=qs.filter(members__employee=actor,members__left_at__isnull=True)
            else: qs=qs.filter(Q(manager=actor)|Q(members__employee=actor,members__left_at__isnull=True))
        if p.get("search"):
            value=p["search"]
            qs=qs.filter(Q(number__icontains=value)|Q(name__icontains=value)|Q(goal__icontains=value))
        return qs.select_related("manager", "customer", "org_unit", "location").order_by("-created_at")

    def list(self, request):
        page=self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(ProjectSerializer(page,many=True).data)

    def retrieve(self, request, pk=None):
        return Response(ProjectSerializer(self.get_object()).data)

    def create(self, request):
        serializer=ProjectSerializer(data=request.data)
        reject_unknown_fields(request.data,serializer)
        serializer.is_valid(raise_exception=True)
        project,created=business_call(lambda:self.idempotent_create("project",{"data":request.data},
            lambda:ProjectService.create(actor=self.actor(),actor_user=request.user,
                correlation_id=self.correlation_id(),**serializer.validated_data)))
        return Response(ProjectSerializer(project).data,status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def partial_update(self, request, pk=None):
        data=ProjectEditSerializer(data=request.data,partial=True);data.is_valid(raise_exception=True)
        reject_unknown_fields(request.data,data)
        values=dict(data.validated_data);version=values.pop("version",None)
        if version is None: raise ValidationError("Укажите version проекта.")
        project=business_call(lambda:ProjectService.edit(project=self.get_object(),actor=self.actor(),
            actor_user=request.user,version=version,changes=values,correlation_id=self.correlation_id()))
        return Response(ProjectSerializer(project).data)

    def _transition(self, request, name):
        data=VersionSerializer(data=request.data);data.is_valid(raise_exception=True)
        project=business_call(lambda:ProjectService.transition(project=self.get_object(),actor=self.actor(),
            actor_user=request.user,version=data.validated_data["version"],action=name,
            reason=data.validated_data.get("reason",""),correlation_id=self.correlation_id()))
        return Response(ProjectSerializer(project).data)

    @action(detail=True,methods=["post"])
    def start(self,request,pk=None):return self._transition(request,"start")

    @action(detail=True,methods=["post"])
    def hold(self,request,pk=None):return self._transition(request,"hold")

    @action(detail=True,methods=["post"])
    def complete(self,request,pk=None):return self._transition(request,"complete")

    @action(detail=True,methods=["post"])
    def cancel(self,request,pk=None):return self._transition(request,"cancel")

    @action(detail=True,methods=["post"])
    def reopen(self,request,pk=None):return self._transition(request,"reopen")

    @action(detail=True,methods=["post"])
    def restore(self,request,pk=None):return self._transition(request,"restore")

    def _archive(self,request,archive):
        data=VersionSerializer(data=request.data);data.is_valid(raise_exception=True)
        project=business_call(lambda:ProjectService.archive(project=self.get_object(),actor=self.actor(),
            actor_user=request.user,version=data.validated_data["version"],archive=archive,
            reason=data.validated_data.get("reason",""),correlation_id=self.correlation_id()))
        return Response(ProjectSerializer(project).data)

    @action(detail=True,methods=["post"])
    def archive(self,request,pk=None):return self._archive(request,True)

    @action(detail=True,methods=["post"])
    def unarchive(self,request,pk=None):return self._archive(request,False)

    @action(detail=True,methods=["get","post"])
    def members(self,request,pk=None):
        project=self.get_object()
        if request.method=="GET":
            return Response(MemberSerializer(project.members.filter(left_at__isnull=True).select_related("employee"),many=True).data)
        data=MemberWriteSerializer(data=request.data);data.is_valid(raise_exception=True)
        employee=get_object_or_404(Employee.objects.filter(is_active=True),pk=data.validated_data["employee"])
        item=business_call(lambda:ProjectService.add_member(project=project,actor=self.actor(),actor_user=request.user,
            version=data.validated_data["version"],employee=employee,role=data.validated_data["role"],
            correlation_id=self.correlation_id()))
        return Response(MemberSerializer(item).data,status=201)

    @action(detail=True,methods=["post"],url_path=r"members/(?P<member_id>[^/.]+)/remove")
    def remove_member(self,request,pk=None,member_id=None):
        project=self.get_object();member=get_object_or_404(ProjectMember.objects.filter(project=project,left_at__isnull=True),pk=member_id)
        data=VersionSerializer(data=request.data);data.is_valid(raise_exception=True)
        business_call(lambda:ProjectService.remove_member(project=project,member=member,actor=self.actor(),
            actor_user=request.user,version=data.validated_data["version"],correlation_id=self.correlation_id()))
        return Response(status=204)

    @action(detail=True,methods=["get","post"])
    def stages(self,request,pk=None):
        project=self.get_object()
        if request.method=="GET":return Response(StageSerializer(project.stages.all(),many=True).data)
        data=StageWriteSerializer(data=request.data);data.is_valid(raise_exception=True)
        values=dict(data.validated_data);version=values.pop("version")
        if values.get("responsible"):
            values["responsible"]=get_object_or_404(Employee.objects.filter(is_active=True),pk=values["responsible"])
        stage=business_call(lambda:ProjectService.create_stage(project=project,actor=self.actor(),actor_user=request.user,
            version=version,correlation_id=self.correlation_id(),**values))
        return Response(StageSerializer(stage).data,status=201)

    @action(detail=True,methods=["post"],url_path=r"stages/(?P<stage_id>[^/.]+)/delete")
    def delete_stage(self,request,pk=None,stage_id=None):
        project=self.get_object();stage=get_object_or_404(ProjectStage.objects.filter(project=project),pk=stage_id)
        data=VersionSerializer(data=request.data);data.is_valid(raise_exception=True)
        business_call(lambda:ProjectService.delete_stage(project=project,stage=stage,actor=self.actor(),
            actor_user=request.user,version=data.validated_data["version"],correlation_id=self.correlation_id()))
        return Response(status=204)

    @action(detail=True,methods=["patch"],url_path=r"stages/(?P<stage_id>[^/.]+)")
    def edit_stage(self,request,pk=None,stage_id=None):
        project=self.get_object();stage=get_object_or_404(ProjectStage.objects.filter(project=project),pk=stage_id)
        data=StageEditSerializer(data=request.data);data.is_valid(raise_exception=True)
        changes=dict(data.validated_data);version=changes.pop("version")
        if changes.get("responsible"):
            changes["responsible"]=get_object_or_404(Employee.objects.filter(is_active=True),pk=changes["responsible"])
        item=business_call(lambda:ProjectService.edit_stage(project=project,stage=stage,actor=self.actor(),
            actor_user=request.user,version=version,changes=changes,correlation_id=self.correlation_id()))
        return Response(StageSerializer(item).data)

    @action(detail=True,methods=["get","post"])
    def milestones(self,request,pk=None):
        project=self.get_object()
        if request.method=="GET":
            return Response(MilestoneSerializer(project.milestones.select_related("stage","responsible").order_by("due_at","id"),many=True).data)
        data=MilestoneWriteSerializer(data=request.data);data.is_valid(raise_exception=True)
        values=dict(data.validated_data);version=values.pop("version")
        stage_id=values.pop("stage",None)
        stage=get_object_or_404(ProjectStage.objects.filter(project=project),pk=stage_id) if stage_id else None
        if values.get("responsible"):
            values["responsible"]=get_object_or_404(Employee.objects.filter(is_active=True),pk=values["responsible"])
        milestone=business_call(lambda:ProjectService.create_milestone(project=project,actor=self.actor(),
            actor_user=request.user,version=version,stage=stage,correlation_id=self.correlation_id(),**values))
        return Response(MilestoneSerializer(milestone).data,status=201)

    def _milestone_action(self,request,milestone_id,name):
        project=self.get_object()
        milestone=get_object_or_404(ProjectMilestone.objects.filter(project=project),pk=milestone_id)
        data=MilestoneActionSerializer(data=request.data);data.is_valid(raise_exception=True)
        item=business_call(lambda:ProjectService.milestone_action(milestone=milestone,actor=self.actor(),
            actor_user=request.user,project_version=data.validated_data["project_version"],
            action=name,comment=data.validated_data.get("comment",""),correlation_id=self.correlation_id()))
        return Response(MilestoneSerializer(item).data)

    @action(detail=True,methods=["patch"],url_path=r"milestones/(?P<milestone_id>[^/.]+)")
    def edit_milestone(self,request,pk=None,milestone_id=None):
        project=self.get_object();milestone=get_object_or_404(ProjectMilestone.objects.filter(project=project),pk=milestone_id)
        data=MilestoneEditSerializer(data=request.data);data.is_valid(raise_exception=True)
        changes=dict(data.validated_data);version=changes.pop("version")
        if "stage" in changes and changes["stage"]:
            changes["stage"]=get_object_or_404(ProjectStage.objects.filter(project=project),pk=changes["stage"])
        if changes.get("responsible"):
            changes["responsible"]=get_object_or_404(Employee.objects.filter(is_active=True),pk=changes["responsible"])
        item=business_call(lambda:ProjectService.edit_milestone(project=project,milestone=milestone,actor=self.actor(),
            actor_user=request.user,version=version,changes=changes,correlation_id=self.correlation_id()))
        return Response(MilestoneSerializer(item).data)

    @action(detail=True,methods=["post"],url_path=r"milestones/(?P<milestone_id>[^/.]+)/confirm")
    def confirm_milestone(self,request,pk=None,milestone_id=None):
        return self._milestone_action(request,milestone_id,"confirm")

    @action(detail=True,methods=["post"],url_path=r"milestones/(?P<milestone_id>[^/.]+)/reopen")
    def reopen_milestone(self,request,pk=None,milestone_id=None):
        return self._milestone_action(request,milestone_id,"reopen")

    def visible_tasks(self, project):
        qs=Task.objects.all() if self.request.user.is_superuser else TaskSelector.visible_to(self.actor())
        return qs.filter(project_link__project=project,project_link__is_active=True)

    @action(detail=True,methods=["get"])
    def tasks(self,request,pk=None):
        page=self.paginate_queryset(self.visible_tasks(self.get_object()).order_by("-created_at"))
        return self.get_paginated_response(TaskSerializer(page,many=True,context={"request":request}).data)

    @action(detail=True,methods=["get"])
    def counters(self,request,pk=None):
        project=self.get_object();qs=self.visible_tasks(project)
        now=timezone.now()
        counts=qs.aggregate(available=Count("pk"),completed=Count("pk",filter=Q(status=TaskStatus.COMPLETED)),
            cancelled=Count("pk",filter=Q(status=TaskStatus.CANCELLED)),
            review=Count("pk",filter=Q(status=TaskStatus.REVIEW)),
            active=Count("pk",filter=Q(status__in=[TaskStatus.OPEN,TaskStatus.IN_PROGRESS,TaskStatus.WAITING])),
            overdue=Count("pk",filter=Q(due_at__lt=now)&~Q(status__in=[TaskStatus.COMPLETED,TaskStatus.CANCELLED])))
        denominator=counts["available"]-counts["cancelled"]
        counts["progress_percent"]=round(counts["completed"]*100/denominator) if denominator else None
        counts["label"]="По доступным задачам" if denominator else "Нет задач"
        counts["scope"]="accessible_tasks"
        counts["by_responsible"]=[{"employee_id":str(row["responsible_employee_id"]) if row["responsible_employee_id"] else None,
                                  "employee_name":" ".join(part for part in (row["responsible_employee__last_name"],row["responsible_employee__first_name"]) if part) or "Не назначен",
                                  "active":row["active"],"overdue":row["overdue"]}
            for row in qs.values("responsible_employee_id","responsible_employee__first_name","responsible_employee__last_name").annotate(
                active=Count("pk",filter=~Q(status__in=[TaskStatus.COMPLETED,TaskStatus.CANCELLED])),
                overdue=Count("pk",filter=Q(due_at__lt=now)&~Q(status__in=[TaskStatus.COMPLETED,TaskStatus.CANCELLED])))]
        counts["next_milestones"]=[{"id":str(m.pk),"name":m.name,"due_at":m.due_at}
            for m in project.milestones.filter(confirmed_at__isnull=True,due_at__gte=now).order_by("due_at")[:5]]
        return Response(counts)

    @action(detail=True,methods=["get"])
    def history(self,request,pk=None):
        project=self.get_object()
        audits=AuditEvent.objects.filter(entity_type="Project",entity_id=str(project.pk)).exclude(
            action__startswith="project.task_").exclude(action="project.reopened_by_task").order_by("-created_at")[:100]
        visible=(Task.objects.all() if request.user.is_superuser else TaskSelector.visible_to(self.actor())).values("pk")
        links=ProjectTaskLinkHistory.objects.filter(Q(old_project=project)|Q(new_project=project),task_id__in=visible)
        return Response({"project":[{"action":event.action,"actor_employee_id":str(event.actor_employee_id) if event.actor_employee_id else None,
                    "created_at":event.created_at,"old":event.old_values,"new":event.new_values} for event in audits],
            "links":[{"task_id":str(item.task_id),"action":item.action,"created_at":item.created_at,
                     "old_stage_id":str(item.old_stage_id) if item.old_stage_id else None,
                     "new_stage_id":str(item.new_stage_id) if item.new_stage_id else None} for item in links.order_by("-created_at")[:100]]})

    @action(detail=True,methods=["post"],url_path="link-task")
    def link_task(self,request,pk=None):
        project=self.get_object();data=LinkSerializer(data=request.data);data.is_valid(raise_exception=True)
        values=data.validated_data
        task=get_object_or_404(TaskSelector.visible_to(self.actor()) if not request.user.is_superuser else Task.objects.all(),pk=values["task"])
        stage=get_object_or_404(ProjectStage.objects.filter(project=project),pk=values["stage"]) if values.get("stage") else None
        link=business_call(lambda:ProjectTaskService.link(project=project,task=task,actor=self.actor(),actor_user=request.user,
            project_version=values["project_version"],task_version=values["task_version"],stage=stage,correlation_id=self.correlation_id()))
        return Response({"task_id":str(link.task_id),"project_id":str(link.project_id),"stage_id":str(link.stage_id) if link.stage_id else None},status=201)

    def linked_task(self, project, task_id):
        qs=Task.objects.all() if self.request.user.is_superuser else TaskSelector.visible_to(self.actor())
        return get_object_or_404(qs.filter(project_link__project=project,project_link__is_active=True),pk=task_id)

    @action(detail=True,methods=["post"],url_path="unlink-task")
    def unlink_task(self,request,pk=None):
        project=self.get_object();data=UnlinkSerializer(data=request.data);data.is_valid(raise_exception=True)
        values=data.validated_data;task=self.linked_task(project,values["task"])
        link=business_call(lambda:ProjectTaskService.unlink(task=task,actor=self.actor(),actor_user=request.user,
            task_version=values["task_version"],project_version=values["project_version"],
            reason=values.get("reason",""),correlation_id=self.correlation_id()))
        return Response({"task_id":str(link.task_id),"linked":False})

    @action(detail=True,methods=["post"],url_path="move-stage")
    def move_stage(self,request,pk=None):
        project=self.get_object();data=MoveStageSerializer(data=request.data);data.is_valid(raise_exception=True)
        values=data.validated_data;task=self.linked_task(project,values["task"])
        stage=get_object_or_404(ProjectStage.objects.filter(project=project),pk=values["stage"]) if values.get("stage") else None
        link=business_call(lambda:ProjectTaskService.move_stage(task=task,stage=stage,actor=self.actor(),actor_user=request.user,
            task_version=values["task_version"],project_version=values["project_version"],correlation_id=self.correlation_id()))
        return Response({"task_id":str(link.task_id),"stage_id":str(link.stage_id) if link.stage_id else None})

    @action(detail=True,methods=["post"],url_path="move-project")
    def move_project(self,request,pk=None):
        source=self.get_object();data=MoveProjectSerializer(data=request.data);data.is_valid(raise_exception=True)
        values=data.validated_data;task=self.linked_task(source,values["task"])
        target=get_object_or_404(ProjectAccessPolicy.visible_to(self.actor(),"project.task_link_manage")
            if not request.user.is_superuser else Project.objects.all(),pk=values["target_project"])
        stage=get_object_or_404(ProjectStage.objects.filter(project=target),pk=values["target_stage"]) if values.get("target_stage") else None
        link=business_call(lambda:ProjectTaskService.move_project(task=task,target_project=target,target_stage=stage,
            actor=self.actor(),actor_user=request.user,task_version=values["task_version"],
            source_version=values["source_version"],target_version=values["target_version"],
            reason=values.get("reason",""),correlation_id=self.correlation_id()))
        return Response({"task_id":str(link.task_id),"project_id":str(link.project_id),"stage_id":str(link.stage_id) if link.stage_id else None})

    @action(detail=True,methods=["post"],url_path="create-task")
    def create_task(self,request,pk=None):
        project=self.get_object();data=ProjectTaskCreateSerializer(data=request.data);data.is_valid(raise_exception=True)
        reject_unknown_fields(request.data,data)
        values=dict(data.validated_data);version=values.pop("project_version")
        stage_id=values.pop("stage",None)
        template_id=values.pop("template",None)
        stage=get_object_or_404(ProjectStage.objects.filter(project=project),pk=stage_id) if stage_id else None
        template=get_object_or_404(TaskTemplate.objects.all(),pk=template_id) if template_id else None
        if not template:
            if not values.get("title"):raise ValidationError("Укажите название задачи.")
            for field in ("responsible_target","executor_target"):
                if values.get(field): values[field]=get_object_or_404(AssignmentTarget.objects.all(),pk=values[field])
            values["source_type"]=SourceType.PROJECT
            values["source_id"]=str(project.pk)
        task,created=business_call(lambda:self.idempotent_create("task",{"project_id":str(project.pk),"data":request.data},
            lambda:ProjectTaskService.create_task(project=project,actor=self.actor(),actor_user=request.user,
                project_version=version,stage=stage,template=template,task_data=values if not template else None,
                correlation_id=self.correlation_id())))
        return Response(TaskDetailSerializer(task,context={"request":request}).data,status=201 if created else 200)

    @action(detail=True,methods=["get","post"])
    def comments(self,request,pk=None):
        project=self.get_object()
        if request.method=="GET":
            return Response(ProjectCommentSerializer(project.comments.select_related("author").all(),many=True).data)
        data=ProjectCommentWriteSerializer(data=request.data);data.is_valid(raise_exception=True)
        employee_ids=data.validated_data["mentions"]
        employees=list(Employee.objects.filter(pk__in=employee_ids,is_active=True))
        if len(set(employee_ids))!=len(employees):raise ValidationError("Упомянутый сотрудник недоступен.")
        item=business_call(lambda:ProjectCollaborationService.comment(project=project,actor=self.actor(),
            actor_user=request.user,body=data.validated_data["body"],mentions=employees,correlation_id=self.correlation_id()))
        return Response(ProjectCommentSerializer(item).data,status=201)

    @action(detail=True,methods=["delete"],url_path=r"comments/(?P<comment_id>[^/.]+)")
    def comment_detail(self,request,pk=None,comment_id=None):
        project=self.get_object();comment=get_object_or_404(ProjectComment.objects.filter(project=project),pk=comment_id)
        business_call(lambda:ProjectCollaborationService.delete_comment(comment=comment,actor=self.actor(),
            actor_user=request.user,correlation_id=self.correlation_id()))
        return Response(status=204)

    @action(detail=True,methods=["get","post"])
    def attachments(self,request,pk=None):
        project=self.get_object()
        if request.method=="GET":
            return Response(ProjectAttachmentSerializer(project.attachments.filter(deleted_at__isnull=True),many=True).data)
        item=business_call(lambda:ProjectCollaborationService.add_attachment(project=project,actor=self.actor(),
            actor_user=request.user,uploaded_file=request.FILES.get("file"),correlation_id=self.correlation_id()))
        return Response(ProjectAttachmentSerializer(item).data,status=201)

    @action(detail=True,methods=["delete"],url_path=r"attachments/(?P<attachment_id>[^/.]+)")
    def attachment_detail(self,request,pk=None,attachment_id=None):
        project=self.get_object()
        item=get_object_or_404(ProjectAttachment.objects.filter(project=project,deleted_at__isnull=True),pk=attachment_id)
        business_call(lambda:ProjectCollaborationService.delete_attachment(attachment=item,actor=self.actor(),
            actor_user=request.user,correlation_id=self.correlation_id()))
        return Response(status=204)

    @action(detail=True,methods=["get"],url_path=r"attachments/(?P<attachment_id>[^/.]+)/download")
    def attachment_download(self,request,pk=None,attachment_id=None):
        project=self.get_object()  # SQL-filtered on every request, even an old download URL.
        item=get_object_or_404(ProjectAttachment.objects.filter(project=project,deleted_at__isnull=True),pk=attachment_id)
        return FileResponse(item.file.open("rb"),as_attachment=True,filename=item.original_filename,content_type=item.content_type)
