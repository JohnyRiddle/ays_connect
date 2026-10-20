from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('work_tasks', '0012_checklist_description')]
    operations = [
        migrations.AddField(model_name='task', name='deleted_at', field=models.DateTimeField(blank=True, db_index=True, null=True)),
    ]
