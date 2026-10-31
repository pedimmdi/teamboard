from django.db import migrations


CREATE_SQL = """
CREATE FUNCTION projects_lock_membership_workspace() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE workspace_key uuid;
BEGIN
    IF TG_TABLE_NAME = 'workspaces_workspacemembership' THEN
        workspace_key := OLD.workspace_id;
    ELSIF TG_TABLE_NAME = 'projects_project' THEN
        workspace_key := NEW.workspace_id;
    ELSE
        SELECT workspace_id INTO workspace_key FROM projects_project
        WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.project_id ELSE NEW.project_id END;
    END IF;
    PERFORM 1 FROM workspaces_workspace WHERE id = workspace_key FOR UPDATE;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER project_membership_workspace_lock BEFORE INSERT OR UPDATE OR DELETE
ON projects_projectmembership FOR EACH ROW EXECUTE FUNCTION projects_lock_membership_workspace();
CREATE TRIGGER workspace_membership_project_lock BEFORE UPDATE OR DELETE
ON workspaces_workspacemembership FOR EACH ROW EXECUTE FUNCTION projects_lock_membership_workspace();
CREATE TRIGGER project_creation_workspace_lock BEFORE INSERT
ON projects_project FOR EACH ROW EXECUTE FUNCTION projects_lock_membership_workspace();

CREATE FUNCTION projects_validate_workspace_membership() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE workspace_key uuid;
BEGIN
    IF TG_TABLE_NAME = 'workspaces_workspacemembership' THEN
        workspace_key := OLD.workspace_id;
    ELSE
        SELECT workspace_id INTO workspace_key FROM projects_project WHERE id = NEW.project_id;
    END IF;
    IF EXISTS (
        SELECT 1 FROM projects_projectmembership pm
        JOIN projects_project p ON p.id = pm.project_id
        WHERE p.workspace_id = workspace_key AND NOT EXISTS (
            SELECT 1 FROM workspaces_workspacemembership wm
            WHERE wm.workspace_id = p.workspace_id AND wm.user_id = pm.user_id
        )
    ) THEN
        RAISE EXCEPTION 'Project members must belong to the workspace.'
        USING ERRCODE = '23514', CONSTRAINT = 'project_membership_requires_workspace';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER project_member_workspace_eligibility AFTER INSERT OR UPDATE
ON projects_projectmembership DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION projects_validate_workspace_membership();
CREATE CONSTRAINT TRIGGER workspace_member_project_eligibility AFTER UPDATE OR DELETE
ON workspaces_workspacemembership DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION projects_validate_workspace_membership();
"""

DROP_SQL = """
DROP TRIGGER workspace_member_project_eligibility ON workspaces_workspacemembership;
DROP TRIGGER project_member_workspace_eligibility ON projects_projectmembership;
DROP TRIGGER project_creation_workspace_lock ON projects_project;
DROP TRIGGER workspace_membership_project_lock ON workspaces_workspacemembership;
DROP TRIGGER project_membership_workspace_lock ON projects_projectmembership;
DROP FUNCTION projects_validate_workspace_membership();
DROP FUNCTION projects_lock_membership_workspace();
"""


def check_existing_memberships(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT 1 FROM projects_projectmembership pm
            JOIN projects_project p ON p.id = pm.project_id
            WHERE NOT EXISTS (SELECT 1 FROM workspaces_workspacemembership wm
                WHERE wm.workspace_id = p.workspace_id AND wm.user_id = pm.user_id)
            LIMIT 1
        """)
        if cursor.fetchone():
            raise RuntimeError("Resolve project memberships outside their workspace before migrating.")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0005_alter_project_description"),
        ("workspaces", "0004_move_content_types"),
    ]
    operations = [
        migrations.RunPython(check_existing_memberships, migrations.RunPython.noop),
        migrations.RunSQL(CREATE_SQL, DROP_SQL),
    ]
