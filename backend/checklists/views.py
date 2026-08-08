from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from tasks.models import Task, TaskHistory
from .models import ChecklistAnswer, ChecklistQuestion, ChecklistRun, ChecklistTemplate, Violation
from .serializers import RunSerializer, TemplateSerializer
from audit.services import record

class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=TemplateSerializer
    def get_queryset(self):
        qs=ChecklistTemplate.objects.filter(is_active=True).select_related("facility").prefetch_related("questions")
        if self.request.query_params.get("haccp")=="true": qs=qs.filter(is_haccp=True)
        return qs

class RunViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=RunSerializer
    def get_queryset(self):
        u=self.request.user; qs=ChecklistRun.objects.select_related("template","assignee","facility").prefetch_related("template__questions","answers__question","violations__question")
        if not (u.is_superuser or u.role_assignments.filter(role__code__in={"manager","facility_manager","admin","auditor","executive","owner"}).exists()): qs=qs.filter(assignee=u)
        return qs
    def _assignee(self,run):
        if run.assignee_id!=self.request.user.id: raise PermissionDenied("Чек-лист назначен другому сотруднику")
    @action(detail=True,methods=["post"])
    def start(self,request,pk=None):
        run=self.get_object(); self._assignee(run)
        if run.status!=ChecklistRun.Status.ASSIGNED: raise ValidationError("Чек-лист уже начат")
        run.status=ChecklistRun.Status.IN_PROGRESS; run.started_at=timezone.now(); run.save(update_fields=["status","started_at"])
        return Response(RunSerializer(run).data)
    @action(detail=True,methods=["post"])
    def complete(self,request,pk=None):
        run=self.get_object(); self._assignee(run)
        if run.status in {ChecklistRun.Status.COMPLETED,ChecklistRun.Status.VIOLATION}: raise ValidationError("Результат уже зафиксирован и неизменяем")
        supplied={int(x["question"]):x for x in request.data.get("answers",[]) if x.get("question")}
        questions=list(run.template.questions.all()); missing=[q.text for q in questions if q.is_required and q.id not in supplied]
        if missing: raise ValidationError({"missing":"Не заполнены обязательные пункты: "+", ".join(missing)})
        failures=[]
        for q in questions:
            if q.id not in supplied: continue
            item=supplied[q.id]; value=item.get("value")
            if q.requires_photo and not item.get("attachment_url"): raise ValidationError({"photo":f"Для пункта «{q.text}» требуется фотография"})
            ChecklistAnswer.objects.create(run=run,question=q,value=value,comment=item.get("comment",""),attachment_url=item.get("attachment_url",""))
            failed=q.question_type==ChecklistQuestion.Type.BOOLEAN and value is False
            if q.question_type in {ChecklistQuestion.Type.NUMBER,ChecklistQuestion.Type.TEMPERATURE,ChecklistQuestion.Type.HUMIDITY}:
                try:
                    number=Decimal(str(value)); failed=(q.min_value is not None and number<q.min_value) or (q.max_value is not None and number>q.max_value)
                except InvalidOperation: raise ValidationError({"value":f"Некорректное число в пункте «{q.text}»"})
            if failed: failures.append((q,item))
        for q,item in failures:
            deadline=timezone.now()+timedelta(hours=4)
            task=Task.objects.create(title=f"Устранить нарушение: {q.text}",description=item.get("comment") or "Нарушение выявлено при прохождении чек-листа",creator=request.user,assignee=request.user,facility=run.facility,zone=run.zone,priority=Task.Priority.HIGH,source=Task.Source.CHECKLIST,status=Task.Status.ASSIGNED,initial_deadline=deadline,deadline=deadline,requires_review=True,is_demo=run.is_demo)
            TaskHistory.objects.create(task=task,actor=request.user,action="created_from_checklist",to_status=task.status,details={"checklist_run":run.id})
            Violation.objects.create(run=run,question=q,description=item.get("comment") or q.text,task=task)
        run.completed_at=timezone.now(); run.score=Decimal(str(round((len(questions)-len(failures))*100/max(len(questions),1),2))); run.status=ChecklistRun.Status.VIOLATION if failures else ChecklistRun.Status.COMPLETED
        run.template_snapshot=TemplateSerializer(run.template).data; run.save(update_fields=["completed_at","score","status","template_snapshot"])
        record(request.user,"checklist.completed",run,new_values={"status":run.status,"score":str(run.score),"violations":len(failures)},request=request)
        return Response(RunSerializer(run).data)
