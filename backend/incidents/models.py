from django.conf import settings
from django.db import models
class Incident(models.Model):
    class Status(models.TextChoices): OPEN="open","Открыт"; NOTIFIED="notified","Уведомление отправлено"; ACKNOWLEDGED="acknowledged","Подтверждён"; IN_PROGRESS="in_progress","В работе"; ESCALATED="escalated","Эскалирован"; NORMALIZED="normalized","Показатель нормализован"; CLOSED="closed","Закрыт"; FALSE_ALARM="false_alarm","Ложное срабатывание"
    sensor=models.ForeignKey("sensors.Sensor",on_delete=models.PROTECT,related_name="incidents");sensor_event=models.OneToOneField("sensors.SensorEvent",on_delete=models.PROTECT,null=True,blank=True,related_name="incident")
    deviation_type=models.CharField(max_length=100);level=models.CharField(max_length=20);started_at=models.DateTimeField();detected_at=models.DateTimeField(auto_now_add=True);peak_value=models.DecimalField(max_digits=12,decimal_places=3,null=True)
    responsible=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="incidents");notified_at=models.DateTimeField(null=True,blank=True);acknowledged_at=models.DateTimeField(null=True,blank=True);normalized_at=models.DateTimeField(null=True,blank=True);closed_at=models.DateTimeField(null=True,blank=True)
    reason=models.TextField(blank=True);comment=models.TextField(blank=True);status=models.CharField(max_length=20,choices=Status.choices,default=Status.OPEN);response_run=models.ForeignKey("checklists.ChecklistRun",on_delete=models.SET_NULL,null=True,blank=True);task=models.ForeignKey("tasks.Task",on_delete=models.SET_NULL,null=True,blank=True,related_name="incidents");is_demo=models.BooleanField(default=False)
    class Meta:ordering=["-detected_at"]
    @property
    def response_seconds(self):return int((self.acknowledged_at-self.detected_at).total_seconds()) if self.acknowledged_at else None
class IncidentHistory(models.Model):
    incident=models.ForeignKey(Incident,on_delete=models.CASCADE,related_name="history");actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True);action=models.CharField(max_length=50);details=models.JSONField(default=dict,blank=True);created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=["-created_at"]
