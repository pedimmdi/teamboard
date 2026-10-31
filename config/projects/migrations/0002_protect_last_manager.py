
from django.db import migrations


CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION projects_require_manager()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_project_id uuid;
BEGIN
    IF TG_TABLE_NAME = 'projects_project' THEN
        target_project_id := NEW.id;
    ELSIF TG_OP = 'DELETE' THEN
        target_project_id := OLD.project_id;
    ELSE
        target_project_id := NEW.project_id;
    END IF;

    -- Serialize checks for the same project.
    PERFORM 1
    FROM projects_project
    WHERE id = target_project_id
    FOR UPDATE;

    -- A deleted project does not require a manager.
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM projects_projectmembership pm
        JOIN workspaces_workspacemembership wm
          ON wm.user_id = pm.user_id
         AND wm.workspace_id = (
             SELECT workspace_id
             FROM projects_project
             WHERE id = target_project_id
         )
        WHERE pm.project_id = target_project_id
          AND pm.role = 'manager'
    ) THEN
        RAISE EXCEPTION
            'A project must have at least one workspace-eligible manager.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'project_requires_manager';
    END IF;

    RETURN NULL;
END;
$$;
"""

CREATE_TRIGGERS = """
CREATE CONSTRAINT TRIGGER project_manager_on_project
AFTER INSERT ON projects_project
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION projects_require_manager();

CREATE CONSTRAINT TRIGGER project_manager_on_membership
AFTER INSERT OR UPDATE OR DELETE ON projects_projectmembership
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION projects_require_manager();

CREATE CONSTRAINT TRIGGER project_manager_on_workspace_membership
AFTER DELETE OR UPDATE ON workspaces_workspacemembership
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION projects_require_manager_for_workspace();
"""

CREATE_WORKSPACE_FUNCTION = """
CREATE OR REPLACE FUNCTION projects_require_manager_for_workspace()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    affected_project record;
BEGIN
    FOR affected_project IN
        SELECT DISTINCT p.id
        FROM projects_project p
        JOIN projects_projectmembership pm
          ON pm.project_id = p.id
        WHERE p.workspace_id = OLD.workspace_id
          AND pm.user_id = OLD.user_id
        ORDER BY p.id
    LOOP
        PERFORM 1
        FROM projects_project
        WHERE id = affected_project.id
        FOR UPDATE;

        IF FOUND AND NOT EXISTS (
            SELECT 1
            FROM projects_projectmembership pm
            JOIN workspaces_workspacemembership wm
              ON wm.user_id = pm.user_id
             AND wm.workspace_id = OLD.workspace_id
            WHERE pm.project_id = affected_project.id
              AND pm.role = 'manager'
        ) THEN
            RAISE EXCEPTION
                'A project must have at least one workspace-eligible manager.'
                USING ERRCODE = '23514',
                      CONSTRAINT = 'project_requires_manager';
        END IF;
    END LOOP;

    RETURN NULL;
END;
$$;
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS project_manager_on_workspace_membership
ON workspaces_workspacemembership;

DROP TRIGGER IF EXISTS project_manager_on_membership
ON projects_projectmembership;

DROP TRIGGER IF EXISTS project_manager_on_project
ON projects_project;

DROP FUNCTION IF EXISTS projects_require_manager_for_workspace();
DROP FUNCTION IF EXISTS projects_require_manager();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_FUNCTION,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=CREATE_WORKSPACE_FUNCTION,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=CREATE_TRIGGERS,
            reverse_sql=DROP_SQL,
        ),
    ]
