from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import DeadlineChangeRequest, RecurrenceRule, Task, TaskAttachment, TaskComment, TaskHistory
from .serializers import AttachmentSerializer, CommentSerializer, DeadlineRequestSerializer, RecurrenceSerializer, TaskDetailSerializer, TaskListSerializer, TaskWriteSerializer
from audit.services import record

class TaskViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        u=self.request.user
        qs=Task.objects.select_related("assignee","creator","facility").prefetch_related("collaborators","observers")
        if not (u.is_superuser or u.role_assignments.filter(role__code__in={"admin","executive","owner","hr"}).exists()):
            qs=qs.filter(Q(assignee=u)|Q(creator=u)|Q(collaborators=u)|Q(observers=u)).distinct()
        p=self.request.query_params
        if p.get("scope")=="my": qs=qs.filter(Q(assignee=u)|Q(collaborators=u)).distinct()
        if p.get("scope")=="created": qs=qs.filter(creator=u)
        if p.get("scope")=="review": qs=qs.filter(status=Task.Status.REVIEW,creator=u)
        for key in ("status","priority","facility_id","department_id","assignee_id","creator_id","source","category"):
            if p.get(key): qs=qs.filter(**{key:p[key]})
        if p.get("overdue")=="true": qs=qs.filter(deadline__lt=timezone.now()).exclude(status__in=[Task.Status.COMPLETED,Task.Status.CLOSED,Task.Status.CANCELLED])
        if p.get("search"): qs=qs.filter(Q(title__icontains=p["search"])|Q(description__icontains=p["search"]))
        return qs
    def get_serializer_class(self):
        if self.action in ("create","update","partial_update"): return TaskWriteSerializer
        return TaskDetailSerializer if self.action=="retrieve" else TaskListSerializer
    def perform_create(self,serializer):
        task=serializer.save(); TaskHistory.objects.create(task=task,actor=self.request.user,action="created",to_status=task.status);record(self.request.user,"task.created",task,new_values={"status":task.status},request=self.request)
    def _assignee(self,task):
        if task.assignee_id!=self.request.user.id: raise PermissionDenied("Действие доступно исполнителю")
    def _creator(self,task):
        if task.creator_id!=self.request.user.id and not self.request.user.is_superuser: raise PermissionDenied("Действие доступно постановщику")
    def _transition(self,task,to_status,action_name,details=None):
        old=task.status; task.status=to_status
        if to_status in {Task.Status.COMPLETED,Task.Status.CLOSED}: task.completed_at=timezone.now()
        task.save(update_fields=["status","completed_at","updated_at"])
        TaskHistory.objects.create(task=task,actor=self.request.user,action=action_name,from_status=old,to_status=to_status,details=details or {})
        record(self.request.user,f"task.{action_name}",task,old_values={"status":old},new_values={"status":to_status},request=self.request)
        return Response(TaskDetailSerializer(task,context={"request":self.request}).data)
    @action(detail=True,methods=["post"])
    def accept(self,request,pk=None):
        task=self.get_object(); self._assignee(task)
        if task.status!=Task.Status.ASSIGNED: raise ValidationError("Принять можно только назначенную задачу")
        return self._transition(task,Task.Status.ACCEPTED,"accepted")
    @action(detail=True,methods=["post"])
    def start(self,request,pk=None):
        task=self.get_object(); self._assignee(task)
        if task.status not in {Task.Status.ASSIGNED,Task.Status.ACCEPTED,Task.Status.RETURNED}: raise ValidationError("Задачу нельзя начать из текущего статуса")
        return self._transition(task,Task.Status.IN_PROGRESS,"started")
    @action(detail=True,methods=["post"])
    def submit(self,request,pk=None):
        task=self.get_object(); self._assignee(task); result=request.data.get("result_text","").strip()
        if task.requires_comment and not result: raise ValidationError("Обязателен комментарий о результате")
        task.result_text=result; task.save(update_fields=["result_text"])
        return self._transition(task,Task.Status.REVIEW if task.requires_review else Task.Status.COMPLETED,"submitted",{"result":result})
    @action(detail=True,methods=["post"])
    def approve(self,request,pk=None):
        task=self.get_object(); self._creator(task)
        if task.status!=Task.Status.REVIEW: raise ValidationError("Задача не находится на проверке")
        return self._transition(task,Task.Status.CLOSED,"approved")
    @action(detail=True,methods=["post"])
    def return_task(self,request,pk=None):
        task=self.get_object(); self._creator(task)
        required=("reason","required_fixes","new_deadline")
        if any(not request.data.get(x) for x in required): raise ValidationError("Укажите причину, исправления и новый срок")
        task.deadline=request.data["new_deadline"]; task.save(update_fields=["deadline"])
        return self._transition(task,Task.Status.RETURNED,"returned",{x:request.data.get(x) for x in required})
    @action(detail=True,methods=["post"])
    def comment(self,request,pk=None):
        text=request.data.get("text","").strip()
        if not text: raise ValidationError("Комментарий не может быть пустым")
        item=TaskComment.objects.create(task=self.get_object(),author=request.user,text=text)
        return Response(CommentSerializer(item).data,status=status.HTTP_201_CREATED)
    @action(detail=True,methods=["post"],url_path="deadline-request")
    def deadline_request(self,request,pk=None):
        task=self.get_object(); self._assignee(task)
        s=DeadlineRequestSerializer(data=request.data); s.is_valid(raise_exception=True); item=s.save(task=task,requester=request.user,current_deadline=task.deadline)
        TaskHistory.objects.create(task=task,actor=request.user,action="deadline_requested",details={"proposed_deadline":str(item.proposed_deadline),"reason_type":item.reason_type})
        return Response(DeadlineRequestSerializer(item).data,status=status.HTTP_201_CREATED)
    @action(detail=True,methods=["post"])
    def attachment(self,request,pk=None):
        task=self.get_object(); uploaded=request.FILES.get("file")
        if not uploaded: raise ValidationError("Выберите файл")
        if uploaded.size>15*1024*1024: raise ValidationError("Максимальный размер файла — 15 МБ")
        item=TaskAttachment.objects.create(task=task,uploader=request.user,file=uploaded,original_name=uploaded.name,content_type=uploaded.content_type or "",size=uploaded.size)
        TaskHistory.objects.create(task=task,actor=request.user,action="attachment_added",details={"name":uploaded.name,"size":uploaded.size})
        return Response(AttachmentSerializer(item).data,status=status.HTTP_201_CREATED)
    @action(detail=True,methods=["get"],url_path=r"attachments/(?P<attachment_id>[^/.]+)/download")
    def download_attachment(self,request,pk=None,attachment_id=None):
        task=self.get_object()
        try: item=task.attachments.get(pk=attachment_id)
        except TaskAttachment.DoesNotExist: raise ValidationError("Файл не найден")
        return FileResponse(item.file.open("rb"),as_attachment=True,filename=item.original_name,content_type=item.content_type or "application/octet-stream")
    @action(detail=True,methods=["post"])
    def recurrence(self,request,pk=None):
        task=self.get_object(); self._creator(task)
        serializer=RecurrenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule,_=RecurrenceRule.objects.update_or_create(task_template=task,defaults=serializer.validated_data)
        return Response(RecurrenceSerializer(rule).data)
