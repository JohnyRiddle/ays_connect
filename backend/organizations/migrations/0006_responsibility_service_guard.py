from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
    CREATE OR REPLACE FUNCTION ays_responsibility_guard() RETURNS trigger AS $$
    BEGIN
      IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Responsibility history cannot be deleted' USING ERRCODE='23514';
      END IF;
      IF current_setting('ays.objects_write', true) IS DISTINCT FROM 'on' THEN
        RAISE EXCEPTION 'Use responsibility domain services' USING ERRCODE='23514';
      END IF;
      IF NOT EXISTS (SELECT 1 FROM organizations_location WHERE id=NEW.location_id AND node_kind='object') THEN
        RAISE EXCEPTION 'Responsibility requires an object' USING ERRCODE='23514';
      END IF;
      IF NEW.valid_to IS NULL AND NOT EXISTS (SELECT 1 FROM employees_employee WHERE id=NEW.employee_id AND is_active AND status NOT IN ('terminated','dismissed','archived','suspended','inactive')) THEN
        RAISE EXCEPTION 'Responsibility requires an active employee' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER ays_responsibility_guard BEFORE INSERT OR UPDATE OR DELETE ON organizations_locationresponsibility
    FOR EACH ROW EXECUTE FUNCTION ays_responsibility_guard();
    """)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0005_objects_guards_and_permissions")]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
