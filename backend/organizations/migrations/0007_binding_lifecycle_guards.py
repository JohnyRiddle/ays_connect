from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
    CREATE OR REPLACE FUNCTION ays_location_binding_guard() RETURNS trigger AS $$
    DECLARE location_uuid uuid; candidate jsonb; previous jsonb; ancestor record;
    BEGIN
      candidate := to_jsonb(NEW);
      IF TG_OP='UPDATE' THEN
        previous := to_jsonb(OLD);
        IF candidate->TG_ARGV[0] IS NOT DISTINCT FROM previous->TG_ARGV[0]
           AND NOT COALESCE(candidate->>'is_active'='true' AND previous->>'is_active'='false', false)
           AND NOT COALESCE(candidate->>'status'='active' AND previous->>'status' IS DISTINCT FROM 'active', false)
           AND NOT COALESCE(candidate ? 'valid_to' AND candidate->>'valid_to' IS NULL AND previous->>'valid_to' IS NOT NULL, false) THEN
          RETURN NEW;
        END IF;
      END IF;
      location_uuid := (candidate->>TG_ARGV[0])::uuid;
      IF location_uuid IS NULL THEN RETURN NEW; END IF;
      PERFORM pg_advisory_xact_lock(719230440101);
      FOR ancestor IN WITH RECURSIVE ancestors AS (
        SELECT id,parent_id,is_archived,is_active,node_kind,ARRAY[id] AS visited FROM organizations_location WHERE id=location_uuid
        UNION ALL SELECT p.id,p.parent_id,p.is_archived,p.is_active,p.node_kind,a.visited||p.id FROM organizations_location p JOIN ancestors a ON p.id=a.parent_id WHERE NOT p.id=ANY(a.visited)
      ) SELECT * FROM ancestors LOOP
        IF ancestor.is_archived OR (ancestor.node_kind <> 'unclassified' AND NOT ancestor.is_active) THEN
          RAISE EXCEPTION 'Unavailable location binding' USING ERRCODE='23514';
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    -- Reproducible historical projection, not a new operational assignment.
    DROP TRIGGER IF EXISTS ays_location_bind_location_id ON performance_performancefact;
    """)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0006_responsibility_service_guard")]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
