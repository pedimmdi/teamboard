from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION tasks_unassign_departing_member()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE tasks_task
        SET assignee_id = NULL
        WHERE project_id = OLD.project_id
          AND assignee_id = OLD.user_id;

        RETURN OLD;
    END IF;

    IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN
        UPDATE tasks_task
        SET assignee_id = NULL
        WHERE project_id = OLD.project_id
          AND assignee_id = OLD.user_id;
    END IF;

    RETURN NEW;
END;
$$;


CREATE OR REPLACE FUNCTION tasks_validate_assignee()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_task RECORD;
BEGIN
    SELECT project_id, assignee_id
    INTO current_task
    FROM tasks_task
    WHERE id = NEW.id;

    IF NOT FOUND OR current_task.assignee_id IS NULL THEN
        RETURN NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM projects_projectmembership pm
        JOIN projects_project p
          ON p.id = pm.project_id
        JOIN workspaces_workspacemembership wm
          ON wm.workspace_id = p.workspace_id
         AND wm.user_id = pm.user_id
        WHERE pm.project_id = current_task.project_id
          AND pm.user_id = current_task.assignee_id
    ) THEN
        RAISE EXCEPTION
            'Task assignee must belong to the project and workspace.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'task_assignee_requires_membership';
    END IF;

    RETURN NULL;
END;
$$;
"""


REVERSE_SQL = """
CREATE OR REPLACE FUNCTION tasks_unassign_departing_member()
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


CREATE OR REPLACE FUNCTION tasks_validate_assignee()
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
"""


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0002_enforce_task_integrity"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
        ),
    ]