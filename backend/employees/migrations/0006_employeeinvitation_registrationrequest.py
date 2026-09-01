import django.db.models.deletion
import django.db.models.functions.text
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("employees", "0005_alter_position_created_at_alter_position_updated_at"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="EmployeeInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("delivery_address", models.EmailField(blank=True, max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="employee_invitations_created", to=settings.AUTH_USER_MODEL)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invitations", to="employees.employee")),
            ],
            options={"indexes": [models.Index(fields=["employee", "expires_at"], name="employees_e_employe_5c6a28_idx")], "constraints": [models.UniqueConstraint(condition=models.Q(("revoked_at__isnull", True), ("used_at__isnull", True)), fields=("employee",), name="one_open_employee_invitation")]},
        ),
        migrations.CreateModel(
            name="RegistrationRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("full_name", models.CharField(max_length=300)),
                ("email", models.EmailField(max_length=254)),
                ("status", models.CharField(choices=[("pending", "Ожидает проверки"), ("approved", "Одобрена"), ("rejected", "Отклонена"), ("expired", "Истекла")], db_index=True, default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_code", models.CharField(blank=True, max_length=80)),
                ("matched_employee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="registration_requests", to="employees.employee")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="registration_requests_reviewed", to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [models.Index(fields=["email", "status", "created_at"], name="employees_r_email_8fe660_idx")], "constraints": [models.UniqueConstraint(django.db.models.functions.text.Lower("email"), condition=models.Q(("status", "pending")), name="one_pending_registration_email")]},
        ),
    ]
