from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from checklists.models import ChecklistQuestion,ChecklistRun,ChecklistTemplate
from tasks.models import Task,TaskHistory
from .models import Incident,IncidentHistory
from .serializers import IncidentSerializer
from audit.services import record
class IncidentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=IncidentSerializer
    def get_queryset(self):
        u=self.request.user;qs=Incident.objects.select_related("sensor__facility","sensor__zone","responsible").prefetch_related("history")
        if u.is_superuser:return qs
        facilities=list(u.role_assignments.values_list("facility_id",flat=True));facilities+=list(u.employee.facilities.values_list("id",flat=True)) if hasattr(u,"employee") else []
        return qs.filter(sensor__facility_id__in=facilities).distinct()
    @action(detail=True,methods=["post"])
    def acknowledge(self,request,pk=None):
        incident=self.get_object()
        if incident.responsible_id and incident.responsible_id!=request.user.id and not request.user.is_superuser:raise PermissionDenied("Инцидент назначен другому сотруднику")
        if incident.status not in {Incident.Status.OPEN,Incident.Status.NOTIFIED}:raise ValidationError("Инцидент уже подтверждён")
        template,_=ChecklistTemplate.objects.get_or_create(name="Диагностика температурного инцидента",facility=incident.sensor.facility,defaults={"category":"Реагирование на инцидент","description":"Проверка оборудования после тревоги датчика","is_mandatory":True,"is_demo":incident.is_demo})
        questions=["Дверь закрыта","Питание присутствует","Компрессор работает","Ошибка на дисплее отсутствует","Посторонний шум отсутствует","Техническая помощь не требуется"]
        for i,text in enumerate(questions,1):ChecklistQuestion.objects.get_or_create(template=template,order=i,defaults={"text":text,"question_type":ChecklistQuestion.Type.BOOLEAN,"is_required":True})
        run=ChecklistRun.objects.create(template=template,assignee=request.user,facility=incident.sensor.facility,zone=incident.sensor.zone,due_at=timezone.now()+timedelta(minutes=15),is_demo=incident.is_demo)
        incident.status=Incident.Status.ACKNOWLEDGED;incident.acknowledged_at=timezone.now();incident.response_run=run;incident.responsible=request.user;incident.save(update_fields=["status","acknowledged_at","response_run","responsible"]);IncidentHistory.objects.create(incident=incident,actor=request.user,action="acknowledged")
        record(request.user,"incident.acknowledged",incident,new_values={"status":incident.status},request=request)
        return Response(IncidentSerializer(incident).data)
    @action(detail=True,methods=["post"])
    def escalate(self,request,pk=None):
        incident=self.get_object()
        if incident.status not in {Incident.Status.ACKNOWLEDGED,Incident.Status.IN_PROGRESS}:raise ValidationError("Сначала подтвердите инцидент")
        deadline=timezone.now()+timedelta(hours=2);task=Task.objects.create(title=f"Диагностика: {incident.sensor.name}",description=request.data.get("comment","Температура не нормализовалась"),creator=request.user,assignee=request.user,facility=incident.sensor.facility,zone=incident.sensor.zone,priority=Task.Priority.CRITICAL,source=Task.Source.INCIDENT,status=Task.Status.ASSIGNED,initial_deadline=deadline,deadline=deadline,requires_review=True,is_demo=incident.is_demo);TaskHistory.objects.create(task=task,actor=request.user,action="created_from_incident",to_status=task.status)
        incident.task=task;incident.status=Incident.Status.ESCALATED;incident.comment=request.data.get("comment","");incident.save(update_fields=["task","status","comment"]);IncidentHistory.objects.create(incident=incident,actor=request.user,action="escalated",details={"task":task.id})
        return Response(IncidentSerializer(incident).data)
    @action(detail=True,methods=["post"])
    def close(self,request,pk=None):
        incident=self.get_object()
        if incident.status!=Incident.Status.NORMALIZED:raise ValidationError("Закрыть можно только нормализованный инцидент")
        incident.status=Incident.Status.CLOSED;incident.closed_at=timezone.now();incident.reason=request.data.get("reason","");incident.save(update_fields=["status","closed_at","reason"]);IncidentHistory.objects.create(incident=incident,actor=request.user,action="closed")
        return Response(IncidentSerializer(incident).data)
