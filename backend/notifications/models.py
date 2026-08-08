from django.conf import settings
from django.db import models
class Notification(models.Model):
    class Type(models.TextChoices):
        TASK="task","Задача"
        CHECKLIST="checklist","Чек-лист"
        INCIDENT="incident","Инцидент"
        SENSOR="sensor","Датчик"
        SYSTEM="system","Система"
        COURSE_ASSIGNED="course_assigned","Курс назначен"
        COURSE_DUE_SOON="course_due_soon","Срок курса приближается"
        COURSE_OVERDUE="course_overdue","Курс просрочен"
        COURSE_COMPLETED="course_completed","Курс завершён"
        ASSESSMENT_FAILED="assessment_failed","Тест не пройден"
        CERTIFICATE_ISSUED="certificate_issued","Сертификат выдан"
        CERTIFICATE_EXPIRING="certificate_expiring","Сертификат истекает"
        CERTIFICATE_EXPIRED="certificate_expired","Сертификат истёк"
        MATERIAL_ACK_REQUIRED="material_ack_required","Требуется ознакомление"
        MATERIAL_ACK_OVERDUE="material_ack_overdue","Ознакомление просрочено"
    class Priority(models.TextChoices): INFO="info","Информация"; WARNING="warning","Предупреждение"; CRITICAL="critical","Критическое"
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="notifications");notification_type=models.CharField(max_length=40,choices=Type.choices);priority=models.CharField(max_length=20,choices=Priority.choices,default=Priority.INFO);title=models.CharField(max_length=200);message=models.TextField();entity_type=models.CharField(max_length=50,blank=True);entity_id=models.PositiveIntegerField(null=True,blank=True);is_read=models.BooleanField(default=False);read_at=models.DateTimeField(null=True,blank=True);telegram_status=models.CharField(max_length=20,default="pending");is_demo=models.BooleanField(default=False);created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=["is_read","-created_at"]
