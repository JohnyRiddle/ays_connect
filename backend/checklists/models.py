from django.conf import settings
from django.db import models

class ChecklistTemplate(models.Model):
    class Frequency(models.TextChoices):
        ONCE="once","Однократно"; DAILY="daily","Ежедневно"; WEEKLY="weekly","Еженедельно"; MONTHLY="monthly","Ежемесячно"
    name=models.CharField(max_length=200); category=models.CharField(max_length=100); description=models.TextField(blank=True)
    version=models.PositiveIntegerField(default=1); facility=models.ForeignKey("organizations.Facility",on_delete=models.CASCADE,related_name="checklist_templates")
    responsible_role=models.CharField(max_length=50,blank=True); frequency=models.CharField(max_length=20,choices=Frequency.choices,default=Frequency.DAILY)
    opens_at=models.TimeField(null=True,blank=True); deadline_time=models.TimeField(null=True,blank=True); is_mandatory=models.BooleanField(default=True)
    default_assignee=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="scheduled_checklist_templates")
    next_run_at=models.DateTimeField(null=True,blank=True)
    escalation_rules=models.JSONField(default=dict,blank=True); is_active=models.BooleanField(default=True); is_haccp=models.BooleanField(default=False); is_demo=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["category","name"]

class ChecklistQuestion(models.Model):
    class Type(models.TextChoices):
        BOOLEAN="boolean","Да / Нет"; TEXT="text","Текст"; NUMBER="number","Число"; TEMPERATURE="temperature","Температура"; HUMIDITY="humidity","Влажность"; RATING="rating","Оценка"; PHOTO="photo","Фотография"; FILE="file","Файл"; SINGLE="single","Один вариант"; MULTIPLE="multiple","Несколько вариантов"; SIGNATURE="signature","Подпись"; ACKNOWLEDGEMENT="acknowledgement","Подтверждение"
    template=models.ForeignKey(ChecklistTemplate,on_delete=models.CASCADE,related_name="questions"); text=models.CharField(max_length=300)
    question_type=models.CharField(max_length=24,choices=Type.choices); order=models.PositiveIntegerField(default=0); is_required=models.BooleanField(default=True)
    requires_photo=models.BooleanField(default=False); options=models.JSONField(default=list,blank=True); min_value=models.DecimalField(max_digits=8,decimal_places=2,null=True,blank=True); max_value=models.DecimalField(max_digits=8,decimal_places=2,null=True,blank=True)
    failure_creates_task=models.BooleanField(default=True)
    class Meta: ordering=["order"]

class ChecklistRun(models.Model):
    class Status(models.TextChoices): ASSIGNED="assigned","Назначен"; IN_PROGRESS="in_progress","В работе"; COMPLETED="completed","Завершён"; VIOLATION="violation","Есть нарушения"; CANCELLED="cancelled","Отменён"
    template=models.ForeignKey(ChecklistTemplate,on_delete=models.PROTECT,related_name="runs"); template_snapshot=models.JSONField(default=dict)
    assignee=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="checklist_runs"); facility=models.ForeignKey("organizations.Facility",on_delete=models.PROTECT)
    zone=models.ForeignKey("organizations.Zone",on_delete=models.SET_NULL,null=True,blank=True); due_at=models.DateTimeField(); started_at=models.DateTimeField(null=True,blank=True); completed_at=models.DateTimeField(null=True,blank=True)
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.ASSIGNED); score=models.DecimalField(max_digits=5,decimal_places=2,null=True,blank=True); is_reinspection=models.BooleanField(default=False); parent_run=models.ForeignKey("self",on_delete=models.SET_NULL,null=True,blank=True)
    is_demo=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True)
    scheduled_for=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=["due_at"]
        constraints=[models.UniqueConstraint(fields=["template","scheduled_for"],condition=models.Q(scheduled_for__isnull=False),name="unique_checklist_schedule_period")]

class ChecklistAnswer(models.Model):
    run=models.ForeignKey(ChecklistRun,on_delete=models.CASCADE,related_name="answers"); question=models.ForeignKey(ChecklistQuestion,on_delete=models.PROTECT)
    value=models.JSONField(); comment=models.TextField(blank=True); attachment_url=models.URLField(blank=True); answered_at=models.DateTimeField(auto_now_add=True)
    class Meta: constraints=[models.UniqueConstraint(fields=["run","question"],name="unique_run_question_answer")]

class Violation(models.Model):
    class Severity(models.TextChoices): LOW="low","Низкая"; MEDIUM="medium","Средняя"; HIGH="high","Высокая"; CRITICAL="critical","Критическая"
    run=models.ForeignKey(ChecklistRun,on_delete=models.PROTECT,related_name="violations"); question=models.ForeignKey(ChecklistQuestion,on_delete=models.PROTECT)
    description=models.TextField(); severity=models.CharField(max_length=20,choices=Severity.choices,default=Severity.HIGH); task=models.ForeignKey("tasks.Task",on_delete=models.SET_NULL,null=True,blank=True,related_name="checklist_violations")
    resolved_at=models.DateTimeField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True)
