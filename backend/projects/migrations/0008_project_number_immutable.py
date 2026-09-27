from django.db import migrations


CREATE = """
CREATE OR REPLACE FUNCTION projects_number_immutable_guard() RETURNS trigger AS $$
BEGIN
    IF NEW.number IS DISTINCT FROM OLD.number THEN
        RAISE EXCEPTION 'Project number is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER project_number_immutable_guard
BEFORE UPDATE OF number ON projects_project
FOR EACH ROW EXECUTE FUNCTION projects_number_immutable_guard();
"""
DROP = """
DROP TRIGGER IF EXISTS project_number_immutable_guard ON projects_project;
DROP FUNCTION IF EXISTS projects_number_immutable_guard();
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql": schema_editor.execute(CREATE)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql": schema_editor.execute(DROP)


class Migration(migrations.Migration):
    dependencies = [("projects", "0007_projectcreaterequest")]
    operations = [migrations.RunPython(install, uninstall)]
