from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge_base", "0001_initial"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="materialacknowledgmentassignment",
            name="requires_test",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(model_name="ttkmetadata", name="dish_category", field=models.CharField(blank=True, max_length=180)),
        migrations.AddField(model_name="ttkmetadata", name="brand", field=models.CharField(blank=True, max_length=180)),
        migrations.AddField(
            model_name="ttkmetadata", name="facility",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ttk_materials", to="organizations.facility"),
        ),
        migrations.AddField(model_name="ttkmetadata", name="workshop", field=models.CharField(blank=True, max_length=180)),
        migrations.AddField(model_name="ttkmetadata", name="yield_unit", field=models.CharField(blank=True, max_length=32)),
        migrations.AddField(model_name="ttkmetadata", name="cooking_time_minutes", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="ttkmetadata", name="storage_temperature", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="ttkmetadata", name="storage_duration", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="ttkmetadata", name="serving_requirements", field=models.TextField(blank=True)),
        migrations.AddField(
            model_name="ttkmetadata", name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_ttk_materials", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(model_name="ttkmetadata", name="effective_from", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="ttkmetadata", name="reference_image", field=models.FileField(blank=True, upload_to="knowledge/ttk/%Y/%m/")),
    ]
