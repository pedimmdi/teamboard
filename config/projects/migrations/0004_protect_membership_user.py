
from django.db import migrations


CREATE_SQL = """
CREATE OR REPLACE FUNCTION projects_prevent_membership_user_transfer()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN
        RAISE EXCEPTION
            'Changing the user of a project membership is not supported.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'project_membership_user_immutable';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER prevent_project_membership_user_transfer
BEFORE UPDATE OF user_id ON projects_projectmembership
FOR EACH ROW
EXECUTE FUNCTION projects_prevent_membership_user_transfer();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS prevent_project_membership_user_transfer
ON projects_projectmembership;

DROP FUNCTION IF EXISTS projects_prevent_membership_user_transfer();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0003_protect_project_relationships"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_SQL,
            reverse_sql=DROP_SQL,
        ),
    ]
