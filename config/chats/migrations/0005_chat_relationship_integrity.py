
from django.db import migrations


CHECK_EXISTING_SQL = """
SELECT 1
FROM chats_conversation AS c
JOIN projects_project AS p ON p.id = c.project_id
WHERE c.workspace_id <> p.workspace_id
LIMIT 1;
"""


CREATE_SQL = """
CREATE OR REPLACE FUNCTION chats_protect_conversation_relationships()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
           OR NEW.project_id IS DISTINCT FROM OLD.project_id
           OR NEW.type IS DISTINCT FROM OLD.type
           OR NEW.direct_user_low_id IS DISTINCT FROM OLD.direct_user_low_id
           OR NEW.direct_user_high_id IS DISTINCT FROM OLD.direct_user_high_id
        THEN
            RAISE EXCEPTION
                'Conversation relationships cannot be changed.'
                USING ERRCODE = '23514',
                      CONSTRAINT = 'chat_conversation_relationships_immutable';
        END IF;
    END IF;

    IF NEW.project_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1
            FROM projects_project AS p
            WHERE p.id = NEW.project_id
              AND p.workspace_id = NEW.workspace_id
        ) THEN
            RAISE EXCEPTION
                'Project and conversation must belong to the same workspace.'
                USING ERRCODE = '23514',
                      CONSTRAINT = 'chat_project_workspace_match';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER chats_conversation_relationship_integrity
BEFORE INSERT OR UPDATE OF
    workspace_id,
    project_id,
    type,
    direct_user_low_id,
    direct_user_high_id
ON chats_conversation
FOR EACH ROW
EXECUTE FUNCTION chats_protect_conversation_relationships();


CREATE OR REPLACE FUNCTION chats_prevent_message_transfer()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.conversation_id IS DISTINCT FROM OLD.conversation_id THEN
        RAISE EXCEPTION
            'Moving a message to another conversation is not supported.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'chat_message_conversation_immutable';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER chats_message_conversation_immutable
BEFORE UPDATE OF conversation_id
ON chats_chatmessage
FOR EACH ROW
EXECUTE FUNCTION chats_prevent_message_transfer();


CREATE OR REPLACE FUNCTION chats_prevent_participant_transfer()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.conversation_id IS DISTINCT FROM OLD.conversation_id
       OR NEW.user_id IS DISTINCT FROM OLD.user_id
    THEN
        RAISE EXCEPTION
            'Conversation participant relationships cannot be changed.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'chat_participant_relationships_immutable';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER chats_participant_relationships_immutable
BEFORE UPDATE OF conversation_id, user_id
ON chats_conversationparticipant
FOR EACH ROW
EXECUTE FUNCTION chats_prevent_participant_transfer();
"""


DROP_SQL = """
DROP TRIGGER IF EXISTS chats_participant_relationships_immutable
ON chats_conversationparticipant;

DROP FUNCTION IF EXISTS chats_prevent_participant_transfer();

DROP TRIGGER IF EXISTS chats_message_conversation_immutable
ON chats_chatmessage;

DROP FUNCTION IF EXISTS chats_prevent_message_transfer();

DROP TRIGGER IF EXISTS chats_conversation_relationship_integrity
ON chats_conversation;

DROP FUNCTION IF EXISTS chats_protect_conversation_relationships();
"""


def check_existing_relationships(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(CHECK_EXISTING_SQL)

        if cursor.fetchone():
            raise RuntimeError(
                "Resolve conversations linked to projects "
                "in another workspace before migrating."
            )


class Migration(migrations.Migration):
    dependencies = [
        ("chats", "0004_chat_integrity_sqlstate"),
        ("projects", "0008_project_avatar"),
    ]

    operations = [
        migrations.RunPython(
            check_existing_relationships,
            migrations.RunPython.noop,
        ),
        migrations.RunSQL(
            sql=CREATE_SQL,
            reverse_sql=DROP_SQL,
        ),
    ]
