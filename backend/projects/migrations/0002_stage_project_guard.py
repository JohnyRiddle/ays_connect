from django.db import migrations


CREATE = """
CREATE OR REPLACE FUNCTION projects_stage_project_guard() RETURNS trigger AS $$
BEGIN
    IF NEW.stage_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM projects_projectstage
        WHERE id = NEW.stage_id AND project_id = NEW.project_id
    ) THEN
        RAISE EXCEPTION 'Project stage belongs to another project' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER project_task_stage_project_guard
BEFORE INSERT OR UPDATE OF project_id, stage_id ON projects_projecttasklink
FOR EACH ROW EXECUTE FUNCTION projects_stage_project_guard();
CREATE TRIGGER project_milestone_stage_project_guard
BEFORE INSERT OR UPDATE OF project_id, stage_id ON projects_projectmilestone
FOR EACH ROW EXECUTE FUNCTION projects_stage_project_guard();
CREATE OR REPLACE FUNCTION projects_stage_project_immutable() RETURNS trigger AS $$
BEGIN
    IF NEW.project_id <> OLD.project_id THEN
        RAISE EXCEPTION 'Project stage cannot move between projects' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER project_stage_project_immutable
BEFORE UPDATE OF project_id ON projects_projectstage
FOR EACH ROW EXECUTE FUNCTION projects_stage_project_immutable();
"""

DROP = """
DROP TRIGGER IF EXISTS project_stage_project_immutable ON projects_projectstage;
DROP FUNCTION IF EXISTS projects_stage_project_immutable();
DROP TRIGGER IF EXISTS project_milestone_stage_project_guard ON projects_projectmilestone;
DROP TRIGGER IF EXISTS project_task_stage_project_guard ON projects_projecttasklink;
DROP FUNCTION IF EXISTS projects_stage_project_guard();
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP)


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial")]
    operations = [migrations.RunPython(install, uninstall)]
