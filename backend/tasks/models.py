from django.conf import settings
from django.db import models
from django.utils import timezone

class Task(models.Model):
    class Status(models.TextChoices):
        DRAFT="draft","Черновик"; ASSIGNED="assigned","Назначена"; ACCEPTED="accepted","Принята"; IN_PROGRESS="in_progress","В работе"; WAITING="waiting","Ожидает информации"; APPROVAL="approval","На согласовании"; REVIEW="review","На проверке"; COMPLETED="completed","Выполнена"; CLOSED="closed","Закрыта"; RETURNED="returned","Возвращена"; CANCELLED="cancelled","Отменена"
    class Priority(models.TextChoices):
        LOW="low","Низкий"; NORMAL="normal","Обычный"; HIGH="high","Высокий"; CRITICAL="critical","Критический"
    class Source(models.TextChoices):
        MANUAL="manual","Ручная постановка"; CHECKLIST="checklist","Чек-лист"; HACCP="haccp","ХАССП"; SENSOR="sensor","Тревога датчика"; INCIDENT="incident","Инцидент"; REQUEST="request","Техническое обращение"; SCHEDULE="schedule","Расписание"; DOCUMENT="document","Документ"; TRAINING="training","Обучение"; INTEGRATION="integration","Интеграция"
    title=models.CharField(max_length=240)
    description=models.TextField(blank=True)
    creator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="created_tasks")
    assignee=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="assigned_tasks")
    collaborators=models.ManyToManyField(settings.AUTH_USER_MODEL,blank=True,related_name="collaborated_tasks")
    observers=models.ManyToManyField(settings.AUTH_USER_MODEL,blank=True,related_name="observed_tasks")
    approvers=models.ManyToManyField(settings.AUTH_USER_MODEL,blank=True,related_name="approval_tasks")
    facility=models.ForeignKey("organizations.Facility",on_delete=models.SET_NULL,null=True,blank=True,related_name="tasks")
    department=models.ForeignKey("organizations.Department",on_delete=models.SET_NULL,null=True,blank=True,related_name="tasks")
    zone=models.ForeignKey("organizations.Zone",on_delete=models.SET_NULL,null=True,blank=True,related_name="tasks")
    parent=models.ForeignKey("self",on_delete=models.CASCADE,null=True,blank=True,related_name="subtasks")
    category=models.CharField(max_length=100,blank=True)
    priority=models.CharField(max_length=20,choices=Priority.choices,default=Priority.NORMAL)
    criticality=models.PositiveSmallIntegerField(default=1)
    complexity=models.PositiveSmallIntegerField(default=1)
    estimated_minutes=models.PositiveIntegerField(default=30)
    planned_start=models.DateTimeField(null=True,blank=True)
    initial_deadline=models.DateTimeField()
    deadline=models.DateTimeField()
    completed_at=models.DateTimeField(null=True,blank=True)
    acceptance_criteria=models.TextField(blank=True)
    requires_review=models.BooleanField(default=True)
    requires_comment=models.BooleanField(default=False)
    requires_photo=models.BooleanField(default=False)
    requires_file=models.BooleanField(default=False)
    source=models.CharField(max_length=20,choices=Source.choices,default=Source.MANUAL)
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    result_text=models.TextField(blank=True)
    recurrence_rule=models.ForeignKey("RecurrenceRule",on_delete=models.SET_NULL,null=True,blank=True,related_name="generated_tasks")
    scheduled_for=models.DateTimeField(null=True,blank=True)
    is_demo=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    @property
    def is_overdue(self): return self.status not in {self.Status.COMPLETED,self.Status.CLOSED,self.Status.CANCELLED} and self.deadline < timezone.now()
    class Meta:
        ordering=["deadline","-priority"]
        constraints=[models.UniqueConstraint(fields=["recurrence_rule","scheduled_for"],condition=models.Q(recurrence_rule__isnull=False),name="unique_recurring_task_period")]

class TaskComment(models.Model):
    task=models.ForeignKey(Task,on_delete=models.CASCADE,related_name="comments")
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    text=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["created_at"]

class TaskAttachment(models.Model):
    task=models.ForeignKey(Task,on_delete=models.CASCADE,related_name="attachments")
    uploader=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    file=models.FileField(upload_to="task_attachments/%Y/%m/")
    original_name=models.CharField(max_length=255)
    content_type=models.CharField(max_length=120,blank=True)
    size=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]

class TaskHistory(models.Model):
    task=models.ForeignKey(Task,on_delete=models.CASCADE,related_name="history")
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    action=models.CharField(max_length=50)
    from_status=models.CharField(max_length=20,blank=True)
    to_status=models.CharField(max_length=20,blank=True)
    details=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]

class DeadlineChangeRequest(models.Model):
    class Reason(models.TextChoices):
        ASSIGNEE="assignee","По вине исполнителя"; MANAGER="manager","По инициативе руководителя"; EMPLOYEE="employee","Зависимость от сотрудника"; DEPARTMENT="department","Зависимость от подразделения"; CONTRACTOR="contractor","Задержка подрядчика"; TECHNICAL="technical","Техническая причина"; FORCE_MAJEURE="force_majeure","Форс-мажор"
    task=models.ForeignKey(Task,on_delete=models.CASCADE,related_name="deadline_requests")
    requester=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    current_deadline=models.DateTimeField()
    proposed_deadline=models.DateTimeField()
    reason_type=models.CharField(max_length=30,choices=Reason.choices)
    reason=models.TextField()
    status=models.CharField(max_length=20,default="pending")
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="reviewed_deadline_requests")
    created_at=models.DateTimeField(auto_now_add=True)

class RecurrenceRule(models.Model):
    class Frequency(models.TextChoices):
        DAILY="daily","Ежедневно"; WEEKLY="weekly","Еженедельно"; MONTHLY="monthly","Ежемесячно"; AFTER_COMPLETION="after_completion","После завершения"; EVENT="event","По событию"
    task_template=models.OneToOneField(Task,on_delete=models.CASCADE,related_name="recurrence")
    frequency=models.CharField(max_length=30,choices=Frequency.choices)
    interval=models.PositiveSmallIntegerField(default=1)
    weekdays=models.JSONField(default=list,blank=True)
    next_run_at=models.DateTimeField(null=True,blank=True)
    is_active=models.BooleanField(default=True)
