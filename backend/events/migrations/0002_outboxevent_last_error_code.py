from django.db import migrations, models


def add_if_missing(apps, schema_editor):
    model = apps.get_model("events", "OutboxEvent")
    with schema_editor.connection.cursor() as cursor:
        columns = schema_editor.connection.introspection.get_table_description(cursor, model._meta.db_table)
    if "last_error_code" not in {column.name for column in columns}:
        schema_editor.add_field(model, model._meta.get_field("last_error_code"))


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]
    operations = [
        # The local DB already has this column. Preserve it and its values.
        migrations.SeparateDatabaseAndState(state_operations=[migrations.AddField(
            model_name="outboxevent", name="last_error_code",
            field=models.CharField(blank=True, default="", max_length=120),
        )]),
        migrations.RunPython(add_if_missing),
    ]
