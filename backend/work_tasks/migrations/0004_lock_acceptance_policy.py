from django.db import migrations, models


def install(apps, schema_editor):
    Task=apps.get_model('work_tasks','Task')
    History=apps.get_model('work_tasks','TaskStatusHistory')
    Task.objects.exclude(status='draft').update(acceptance_policy_locked=True)
    Task.objects.filter(pk__in=History.objects.exclude(to_status='draft').values('task_id')).update(acceptance_policy_locked=True)
    if schema_editor.connection.vendor=='postgresql':
        schema_editor.execute('''
        CREATE FUNCTION work_task_acceptance_guard() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'UPDATE' THEN
            IF (OLD.acceptance_policy_locked OR OLD.status <> 'draft')
               AND NEW.acceptance_policy IS DISTINCT FROM OLD.acceptance_policy THEN
              RAISE EXCEPTION 'task_acceptance_policy_frozen' USING ERRCODE='23514';
            END IF;
            NEW.acceptance_policy_locked := OLD.acceptance_policy_locked OR OLD.status <> 'draft'
                OR NEW.status <> 'draft';
          ELSE
            NEW.acceptance_policy_locked := NEW.status <> 'draft';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER work_task_acceptance_guard BEFORE INSERT OR UPDATE ON work_tasks_task
        FOR EACH ROW EXECUTE FUNCTION work_task_acceptance_guard();
        ''')
    elif schema_editor.connection.vendor=='sqlite':
        schema_editor.execute("""CREATE TRIGGER work_task_acceptance_guard BEFORE UPDATE ON work_tasks_task
        WHEN (OLD.acceptance_policy_locked OR OLD.status <> 'draft') AND NEW.acceptance_policy <> OLD.acceptance_policy
        BEGIN SELECT RAISE(ABORT, 'task_acceptance_policy_frozen'); END""")
        schema_editor.execute("""CREATE TRIGGER work_task_acceptance_sticky AFTER UPDATE ON work_tasks_task
        WHEN (OLD.acceptance_policy_locked OR OLD.status <> 'draft' OR NEW.status <> 'draft') AND NOT NEW.acceptance_policy_locked
        BEGIN UPDATE work_tasks_task SET acceptance_policy_locked=1 WHERE id=NEW.id; END""")
        schema_editor.execute("""CREATE TRIGGER work_task_acceptance_insert AFTER INSERT ON work_tasks_task
        WHEN NEW.status <> 'draft' AND NOT NEW.acceptance_policy_locked
        BEGIN UPDATE work_tasks_task SET acceptance_policy_locked=1 WHERE id=NEW.id; END""")
    else:
        raise RuntimeError('Acceptance policy guard requires a supported PostgreSQL or SQLite database')


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor=='postgresql':
        schema_editor.execute('DROP TRIGGER IF EXISTS work_task_acceptance_guard ON work_tasks_task; DROP FUNCTION IF EXISTS work_task_acceptance_guard();')
    elif schema_editor.connection.vendor=='sqlite':
        for name in ('work_task_acceptance_guard','work_task_acceptance_sticky','work_task_acceptance_insert'):
            schema_editor.execute('DROP TRIGGER IF EXISTS '+name)


class Migration(migrations.Migration):
    dependencies=[('work_tasks','0003_alter_task_source_type_taskrecurrencerule_and_more')]
    operations=[migrations.AddField(model_name='task',name='acceptance_policy_locked',field=models.BooleanField(default=False,editable=False)),migrations.RunPython(install,uninstall)]
