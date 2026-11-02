
from django.db import migrations


CREATE_SQL = """
CREATE FUNCTION tasks_protect_relationships()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.project_id IS DISTINCT FROM OLD.project_id THEN
        RAISE EXCEPTION
            'Moving a task to another project is not supported.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'task_project_immutable';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER prevent_task_project_transfer
BEFORE UPDATE OF project_id ON tasks_task
FOR EACH ROW
EXECUTE FUNCTION tasks_protect_relationships();


CREATE FUNCTION tasks_lock_workspace()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    workspace_key uuid;
BEGIN
    SELECT workspace_id
    INTO workspace_key
    FROM projects_project
    WHERE id = NEW.project_id;

    PERFORM 1
    FROM workspaces_workspace
    WHERE id = workspace_key
    FOR UPDATE;

    RETURN NEW;
END;
$$;

CREATE TRIGGER task_workspace_lock
BEFORE INSERT OR UPDATE OF project_id, assignee_id
ON tasks_task
FOR EACH ROW
EXECUTE FUNCTION tasks_lock_workspace();


CREATE FUNCTION tasks_validate_assignee()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.assignee_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM projects_projectmembership pm
           JOIN projects_project p
             ON p.id = pm.project_id
           JOIN workspaces_workspacemembership wm
             ON wm.workspace_id = p.workspace_id
            AND wm.user_id = pm.user_id
           WHERE pm.project_id = NEW.project_id
             AND pm.user_id = NEW.assignee_id
       )
    THEN
        RAISE EXCEPTION
            'Task assignee must belong to the project and workspace.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'task_assignee_requires_membership';
    END IF;

    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER task_assignee_eligibility
AFTER INSERT OR UPDATE OF project_id, assignee_id
ON tasks_task
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION tasks_validate_assignee();


CREATE FUNCTION tasks_unassign_departing_member()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE tasks_task
    SET assignee_id = NULL
    WHERE project_id = OLD.project_id
      AND assignee_id = OLD.user_id;

    RETURN OLD;
END;
$$;

CREATE TRIGGER unassign_departing_project_member
BEFORE DELETE OR UPDATE OF user_id
ON projects_projectmembership
FOR EACH ROW
EXECUTE FUNCTION tasks_unassign_departing_member();
"""


DROP_SQL = """
DROP TRIGGER IF EXISTS unassign_departing_project_member
ON projects_projectmembership;

DROP TRIGGER IF EXISTS task_assignee_eligibility
ON tasks_task;

DROP TRIGGER IF EXISTS task_workspace_lock
ON tasks_task;

DROP TRIGGER IF EXISTS prevent_task_project_transfer
ON tasks_task;

DROP FUNCTION IF EXISTS tasks_unassign_departing_member();
DROP FUNCTION IF EXISTS tasks_validate_assignee();
DROP FUNCTION IF EXISTS tasks_lock_workspace();
DROP FUNCTION IF EXISTS tasks_protect_relationships();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0001_initial"),
        ("projects", "0006_enforce_workspace_membership"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_SQL,
            reverse_sql=DROP_SQL,
        ),
    ]
