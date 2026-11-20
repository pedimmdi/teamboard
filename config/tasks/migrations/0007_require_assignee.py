"""Keep every current task assigned; historical snapshots remain unchanged."""
from importlib import import_module
from django.db import migrations, models

SQL = """
CREATE FUNCTION tasks_assign_required() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.assignee_id IS NULL THEN
        SELECT pm.user_id INTO NEW.assignee_id
        FROM projects_projectmembership pm
        JOIN projects_project p ON p.id = pm.project_id
        JOIN workspaces_workspacemembership wm
          ON wm.workspace_id = p.workspace_id AND wm.user_id = pm.user_id
        WHERE pm.project_id = NEW.project_id AND pm.role = 'manager'
          AND (TG_OP = 'INSERT' OR pm.user_id IS DISTINCT FROM OLD.assignee_id)
        ORDER BY pm.user_id LIMIT 1;
        IF NEW.assignee_id IS NULL THEN
            RAISE EXCEPTION 'Task requires an eligible project manager as fallback assignee.'
            USING ERRCODE = '23514', CONSTRAINT = 'task_assignee_required';
        END IF;
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER task_assign_required BEFORE INSERT OR UPDATE OF assignee_id ON tasks_task
FOR EACH ROW EXECUTE FUNCTION tasks_assign_required();

CREATE OR REPLACE FUNCTION tasks_unassign_departing_member() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE replacement bigint;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id THEN RETURN NEW; END IF;
    -- During project cascade deletion there is no surviving task to reassign.
    IF EXISTS (SELECT 1 FROM projects_project WHERE id = OLD.project_id)
       AND EXISTS (SELECT 1 FROM tasks_task WHERE project_id = OLD.project_id AND assignee_id = OLD.user_id) THEN
        SELECT pm.user_id INTO replacement FROM projects_projectmembership pm
        JOIN projects_project p ON p.id = pm.project_id
        JOIN workspaces_workspacemembership wm ON wm.workspace_id = p.workspace_id AND wm.user_id = pm.user_id
        WHERE pm.project_id = OLD.project_id AND pm.user_id <> OLD.user_id AND pm.role = 'manager'
        ORDER BY pm.user_id LIMIT 1;
        IF replacement IS NOT NULL THEN
            UPDATE tasks_task SET assignee_id = replacement, updated_at = clock_timestamp()
            WHERE project_id = OLD.project_id AND assignee_id = OLD.user_id;
        END IF;
        -- Without a replacement defer validation: a cascading Workspace/Project
        -- deletion can remove memberships before it removes their tasks.
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END; $$;
CREATE FUNCTION tasks_check_departure() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM tasks_task t
        WHERE t.project_id = OLD.project_id AND t.assignee_id = OLD.user_id
          AND NOT EXISTS (
              SELECT 1 FROM projects_projectmembership pm
              JOIN projects_project p ON p.id = pm.project_id
              JOIN workspaces_workspacemembership wm ON wm.workspace_id = p.workspace_id AND wm.user_id = pm.user_id
              WHERE pm.project_id = t.project_id AND pm.user_id = t.assignee_id
          )
    ) THEN
        RAISE EXCEPTION 'Transfer assigned tasks to a remaining project manager first.'
        USING ERRCODE = '23514', CONSTRAINT = 'task_assignee_required';
    END IF;
    RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER task_departure_assignment_check
AFTER DELETE OR UPDATE OF user_id ON projects_projectmembership
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION tasks_check_departure();
-- Existing unassigned tasks receive the lowest-ID eligible project manager.
UPDATE tasks_task SET assignee_id = NULL WHERE assignee_id IS NULL;
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
"""

class Migration(migrations.Migration):
    dependencies = [("tasks", "0006_track_task_status")]
    operations = [
        migrations.RunSQL(SQL, "DROP TRIGGER IF EXISTS task_departure_assignment_check ON projects_projectmembership; DROP FUNCTION IF EXISTS tasks_check_departure(); DROP TRIGGER task_assign_required ON tasks_task; DROP FUNCTION tasks_assign_required();" + import_module("tasks.migrations.0003_fix_task_integrity_triggers").FORWARD_SQL),
        migrations.AddConstraint(model_name="task", constraint=models.CheckConstraint(condition=models.Q(assignee__isnull=False), name="task_assignee_required")),
    ]
