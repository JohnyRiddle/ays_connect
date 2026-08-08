from datetime import timedelta
from django.db.models import Avg,Count,Q
from django.utils import timezone
from checklists.models import ChecklistRun
from employees.models import Employee
from incidents.models import Incident
from tasks.models import Task,TaskHistory
from learning.models import Certificate,CourseAssignment
from knowledge_base.models import MaterialAcknowledgmentAssignment
def employee_metrics(employee,days=30):
    since=timezone.now()-timedelta(days=days);user=employee.user
    tasks=Task.objects.filter(assignee=user,created_at__gte=since);finished=tasks.filter(status__in=[Task.Status.COMPLETED,Task.Status.CLOSED]);finished_count=finished.count()
    on_time=sum(1 for t in finished if t.completed_at and t.completed_at<=t.deadline);timeliness=round(on_time*100/finished_count,1) if finished_count else 100.0
    returned=TaskHistory.objects.filter(task__assignee=user,task__created_at__gte=since,action="returned").count();quality=max(0,round(100-returned*12.5,1))
    checks=ChecklistRun.objects.filter(assignee=user,completed_at__gte=since,score__isnull=False);check_score=float(checks.aggregate(v=Avg("score"))["v"] or 100)
    incidents=Incident.objects.filter(responsible=user,detected_at__gte=since,acknowledged_at__isnull=False);response_avg=incidents.aggregate(v=Avg("acknowledged_at"))["v"] if False else None
    response_values=[x.response_seconds for x in incidents if x.response_seconds is not None];response_seconds=round(sum(response_values)/len(response_values)) if response_values else None;response_score=100 if response_seconds is None else max(0,round(100-response_seconds/18,1))
    score=round(timeliness*.4+quality*.25+check_score*.2+response_score*.15,1)
    learning=CourseAssignment.objects.filter(employee=employee,is_mandatory=True);learning_completed=learning.filter(status=CourseAssignment.Status.COMPLETED);learning_on_time=sum(1 for x in learning_completed if not x.due_at or (x.completed_at and x.completed_at<=x.due_at));learning_rate=round(learning_on_time*100/learning.count(),1) if learning.exists() else 100.0
    acknowledgments=MaterialAcknowledgmentAssignment.objects.filter(employee=employee);ack_done=acknowledgments.filter(status=MaterialAcknowledgmentAssignment.Status.ACKNOWLEDGED).count();ack_rate=round(ack_done*100/acknowledgments.count(),1) if acknowledgments.exists() else 100.0
    valid_certificates=Certificate.objects.filter(employee=employee,status__in=[Certificate.Status.ACTIVE,Certificate.Status.EXPIRING]).count()
    return {"employee_id":employee.id,"full_name":user.get_full_name(),"position":employee.position,"department":employee.department.name if employee.department else None,"score":score,"timeliness":timeliness,"quality":quality,"checklist_score":round(check_score,1),"response_score":response_score,"avg_response_seconds":response_seconds,"active_tasks":tasks.exclude(status__in=[Task.Status.CLOSED,Task.Status.COMPLETED,Task.Status.CANCELLED]).count(),"completed_tasks":finished_count,"overdue_tasks":tasks.filter(deadline__lt=timezone.now()).exclude(status__in=[Task.Status.CLOSED,Task.Status.COMPLETED,Task.Status.CANCELLED]).count(),"returned_tasks":returned,"mandatory_learning_on_time":learning_rate,"overdue_courses":learning.filter(status=CourseAssignment.Status.OVERDUE).count(),"valid_certificates":valid_certificates,"acknowledgment_rate":ack_rate,"overdue_acknowledgments":acknowledgments.filter(status=MaterialAcknowledgmentAssignment.Status.OVERDUE).count()}
def company_dashboard(company):
    employees=Employee.objects.filter(company=company,user__isnull=False).select_related("user","department");rows=[employee_metrics(e) for e in employees];avg=round(sum(x["score"] for x in rows)/len(rows),1) if rows else 0
    facilities=[]
    for facility in company.regions.values_list("clusters__facilities__id",flat=True):
        from organizations.models import Facility
        f=Facility.objects.filter(id=facility).first()
        if f:facilities.append({"id":f.id,"name":f.name,"active_tasks":f.tasks.exclude(status__in=[Task.Status.CLOSED,Task.Status.COMPLETED,Task.Status.CANCELLED]).count(),"open_incidents":f.sensors.filter(incidents__status__in=[Incident.Status.OPEN,Incident.Status.NOTIFIED,Incident.Status.ACKNOWLEDGED,Incident.Status.ESCALATED]).count(),"checklist_score":round(float(ChecklistRun.objects.filter(facility=f,score__isnull=False).aggregate(v=Avg("score"))["v"] or 100),1)})
    return {"company":{"id":company.id,"name":company.name},"summary":{"employee_count":len(rows),"average_score":avg,"active_tasks":sum(x["active_tasks"] for x in rows),"overdue_tasks":sum(x["overdue_tasks"] for x in rows),"open_incidents":Incident.objects.filter(sensor__facility__cluster__region__company=company).exclude(status__in=[Incident.Status.CLOSED,Incident.Status.FALSE_ALARM]).count()},"employees":sorted(rows,key=lambda x:x["score"],reverse=True),"facilities":facilities}
