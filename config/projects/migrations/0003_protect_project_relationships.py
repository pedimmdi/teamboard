
from django.db import migrations


CREATE_SQL = """
CREATE OR REPLACE FUNCTION projects_prevent_relationship_transfer()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'projects_project' THEN
        IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id THEN
            RAISE EXCEPTION
                'Moving a project to another workspace is not supported.'
                USING ERRCODE = '23514',
                      CONSTRAINT = 'project_workspace_immutable';
        END IF;

    ELSIF TG_TABLE_NAME = 'projects_projectmembership' THEN
        IF NEW.project_id IS DISTINCT FROM OLD.project_id THEN
            RAISE EXCEPTION
                'Moving a membership to another project is not supported.'
                USING ERRCODE = '23514',
                      CONSTRAINT = 'project_membership_project_immutable';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER prevent_project_workspace_transfer
BEFORE UPDATE OF workspace_id ON projects_project
FOR EACH ROW
EXECUTE FUNCTION projects_prevent_relationship_transfer();

CREATE TRIGGER prevent_project_membership_transfer
BEFORE UPDATE OF project_id ON projects_projectmembership
FOR EACH ROW
EXECUTE FUNCTION projects_prevent_relationship_transfer();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS prevent_project_membership_transfer
ON projects_projectmembership;

DROP TRIGGER IF EXISTS prevent_project_workspace_transfer
ON projects_project;

DROP FUNCTION IF EXISTS projects_prevent_relationship_transfer();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_protect_last_manager"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_SQL,
            reverse_sql=DROP_SQL,
        ),
    ]
