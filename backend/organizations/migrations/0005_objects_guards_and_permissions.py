from django.db import migrations


PERMISSIONS = {
    "location.create": "Добавление объектов", "location.edit": "Изменение объектов",
    "location.manage_zones": "Управление зонами", "location.assign_responsible": "Назначение ответственных",
    "location.change_status": "Статусы объектов", "location.archive": "Архив объектов",
    "location.restore": "Восстановление объектов", "location.move": "Перемещение зон",
}


SQL = """
CREATE SEQUENCE IF NOT EXISTS organizations_object_code_seq;
CREATE OR REPLACE FUNCTION ays_location_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.node_kind <> 'unclassified' THEN
      RAISE EXCEPTION 'Managed locations cannot be deleted' USING ERRCODE='23514';
    END IF;
    RETURN OLD;
  END IF;
  IF NEW.node_kind <> 'unclassified' OR (TG_OP = 'UPDATE' AND OLD.node_kind <> 'unclassified') THEN
    PERFORM pg_advisory_xact_lock(719230440101);
    IF current_setting('ays.objects_write', true) IS DISTINCT FROM 'on' THEN
      RAISE EXCEPTION 'Use location domain services' USING ERRCODE='23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.node_kind <> 'unclassified' THEN
      IF NEW.code IS DISTINCT FROM OLD.code OR NEW.node_kind <> OLD.node_kind OR NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'Immutable identity or stale version' USING ERRCODE='23514';
      END IF;
    END IF;
    IF NEW.node_kind = 'object' AND (NEW.code IS NULL OR NEW.code = '' OR NEW.business_type = '' OR NEW.business_status = '') THEN
      RAISE EXCEPTION 'Object contract is incomplete' USING ERRCODE='23514';
    END IF;
    IF NEW.node_kind = 'zone' AND NEW.parent_id IS NULL THEN
      RAISE EXCEPTION 'Zone requires a parent' USING ERRCODE='23514';
    END IF;
    IF NEW.parent_id IS NOT NULL THEN
      IF NOT EXISTS (SELECT 1 FROM organizations_location p WHERE p.id=NEW.parent_id AND NOT p.is_archived AND p.is_active AND (
        (p.node_kind='geography' AND NEW.node_kind IN ('geography','site','object')) OR
        (p.node_kind='site' AND NEW.node_kind='object') OR
        (p.node_kind IN ('object','zone') AND NEW.node_kind='zone'))) THEN
        RAISE EXCEPTION 'Invalid location parent' USING ERRCODE='23514';
      END IF;
      IF EXISTS (WITH RECURSIVE ancestors AS (
        SELECT id,parent_id,ARRAY[id] AS visited FROM organizations_location WHERE id=NEW.parent_id
        UNION ALL SELECT p.id,p.parent_id,a.visited||p.id FROM organizations_location p JOIN ancestors a ON p.id=a.parent_id WHERE NOT p.id=ANY(a.visited)
      ) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN
        RAISE EXCEPTION 'Location cycle' USING ERRCODE='23514';
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER ays_location_guard BEFORE INSERT OR UPDATE OR DELETE ON organizations_location
FOR EACH ROW EXECUTE FUNCTION ays_location_guard();

CREATE OR REPLACE FUNCTION ays_location_binding_guard() RETURNS trigger AS $$
DECLARE location_uuid uuid; candidate jsonb; ancestor record;
BEGIN
  candidate := to_jsonb(NEW);
  IF TG_OP='UPDATE' AND candidate->TG_ARGV[0] IS NOT DISTINCT FROM to_jsonb(OLD)->TG_ARGV[0] THEN RETURN NEW; END IF;
  location_uuid := (candidate->>TG_ARGV[0])::uuid;
  IF location_uuid IS NULL THEN RETURN NEW; END IF;
  PERFORM pg_advisory_xact_lock(719230440101);
  FOR ancestor IN WITH RECURSIVE ancestors AS (
    SELECT id,parent_id,is_archived,is_active,ARRAY[id] AS visited FROM organizations_location WHERE id=location_uuid
    UNION ALL SELECT p.id,p.parent_id,p.is_archived,p.is_active,a.visited||p.id FROM organizations_location p JOIN ancestors a ON p.id=a.parent_id WHERE NOT p.id=ANY(a.visited)
  ) SELECT * FROM ancestors LOOP
    IF ancestor.is_archived OR NOT ancestor.is_active THEN
      RAISE EXCEPTION 'Unavailable location binding' USING ERRCODE='23514';
    END IF;
  END LOOP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def install(apps, schema_editor):
    Permission = apps.get_model("access_control", "Permission")
    for code, name in PERMISSIONS.items():
        Permission.objects.get_or_create(code=code, defaults={"name": name})
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(SQL)
    Location = apps.get_model("organizations", "Location")
    for model in apps.get_models():
        if model is Location or model._meta.label == "organizations.LocationIdempotency":
            continue
        for field in model._meta.concrete_fields:
            if field.is_relation and field.remote_field.model is Location:
                name = f"ays_location_bind_{field.column}"
                schema_editor.execute(f'CREATE TRIGGER {schema_editor.quote_name(name)} BEFORE INSERT OR UPDATE ON {schema_editor.quote_name(model._meta.db_table)} FOR EACH ROW EXECUTE FUNCTION ays_location_binding_guard(\'{field.column}\')')


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0004_location_address_location_business_status_and_more"),
        ("access_control", "0003_alter_rolepermission_scope"),
        ("projects", "0001_initial"),
        ("employees", "0015_employee_account_access_state"),
        ("work_tasks", "0004_lock_acceptance_policy"),
        ("service_requests", "0004_servicerequestcomment_servicerequestcommentmention_and_more"),
        ("sla", "0003_escalationpolicy_escalationpolicyversion_and_more"),
        ("performance", "0002_performanceeventreceipt"),
    ]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
