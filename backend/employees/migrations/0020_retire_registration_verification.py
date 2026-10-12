from django.db import migrations, models
from django.utils import timezone


def retire(apps, schema_editor):
    Request = apps.get_model("employees", "RegistrationRequest")
    Audit = apps.get_model("audit", "AuditEvent")
    Event = apps.get_model("events", "OutboxEvent")
    now = timezone.now()
    for item in Request.objects.filter(employment_location__isnull=False, status="email_pending"):
        item.status = "cancelled"
        item.password_hash = ""
        item.save(update_fields=["status", "password_hash"])
        Audit.objects.create(action="registration.verification_retired", entity_type="RegistrationRequest",
            entity_id=str(item.pk), old_values={"status":"email_pending"}, new_values={"status":"cancelled", "reason":"registration_policy_changed"})
        Event.objects.create(event_type="registration.cancelled", entity_type="RegistrationRequest",
            entity_id=str(item.pk), occurred_at=now, payload={"reason":"registration_policy_changed"})
    Event.objects.filter(event_type__in=["registration.mail.requested", "registration.invite_mail.requested"]).exclude(status="processed").update(
        status="failed", last_error_code="REGISTRATION_MAIL_DISABLED", next_attempt_at=None, failed_at=now)


class Migration(migrations.Migration):
    dependencies = [("employees", "0019_registration_shared_rate_limit"),
        ("audit", "0002_auditevent_actor_employee_auditevent_correlation_id_and_more"),
        ("events", "0002_outboxevent_failed_at_outboxevent_last_error_code_and_more")]
    operations = [migrations.RunPython(retire, migrations.RunPython.noop),
        migrations.AlterField(model_name="registrationrequest", name="status",
            field=models.CharField(choices=[("pending", "Ожидает проверки"), ("approved", "Одобрена"),
                ("rejected", "Отклонена"), ("expired", "Истекла"), ("cancelled", "Отменена")],
                db_index=True, default="pending", max_length=20))]
