from django.db import migrations
def forward(apps,schema_editor):
    Permission=apps.get_model("access_control","Permission");Template=apps.get_model("notifications","NotificationTemplate");Notification=apps.get_model("notifications","Notification")
    for code,name in (("notification.template.view","View notification templates"),("notification.template.manage","Manage notification templates"),("notification.delivery.view","View notification deliveries"),("notification.delivery.manage","Manage notification deliveries")):Permission.objects.get_or_create(code=code,defaults={"name":name})
    Template.objects.get_or_create(code="SLA_ESCALATION",defaults={"name":"SLA escalation","title_template":"SLA: заявка {request_id}","body_template":"Нарушение SLA, уровень {level}. Событие: {event_type}.","allowed_variables":["request_id","level","event_type"]})
    for item in Notification.objects.filter(recipient_employee__isnull=True).select_related("recipient"):
        try:item.recipient_employee_id=item.recipient.employee.pk;item.save(update_fields=["recipient_employee"])
        except Exception:pass
class Migration(migrations.Migration):
    dependencies=[("notifications","0003_notificationintent_notificationtemplate_and_more"),("access_control","0002_initial")];operations=[migrations.RunPython(forward,migrations.RunPython.noop)]
