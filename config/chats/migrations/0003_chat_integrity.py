
from django.db import migrations


CREATE_TRIGGERS = """
CREATE OR REPLACE FUNCTION chats_validate_message_reply()
RETURNS trigger AS $$
BEGIN
    IF NEW.reply_to_id IS NOT NULL THEN
        IF NEW.reply_to_id = NEW.id THEN
            RAISE EXCEPTION 'A message cannot reply to itself';
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM chats_chatmessage AS parent
            WHERE parent.id = NEW.reply_to_id
              AND parent.conversation_id = NEW.conversation_id
        ) THEN
            RAISE EXCEPTION
                'Reply must belong to the same conversation';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER chats_message_reply_integrity
BEFORE INSERT OR UPDATE OF reply_to_id, conversation_id
ON chats_chatmessage
FOR EACH ROW
EXECUTE FUNCTION chats_validate_message_reply();


CREATE OR REPLACE FUNCTION chats_validate_last_read()
RETURNS trigger AS $$
BEGIN
    IF NEW.last_read_message_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1
            FROM chats_chatmessage AS message
            WHERE message.id = NEW.last_read_message_id
              AND message.conversation_id = NEW.conversation_id
        ) THEN
            RAISE EXCEPTION
                'Last read message must belong to the same conversation';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER chats_participant_last_read_integrity
BEFORE INSERT OR UPDATE OF last_read_message_id, conversation_id
ON chats_conversationparticipant
FOR EACH ROW
EXECUTE FUNCTION chats_validate_last_read();
"""


DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS chats_participant_last_read_integrity
ON chats_conversationparticipant;

DROP FUNCTION IF EXISTS chats_validate_last_read();

DROP TRIGGER IF EXISTS chats_message_reply_integrity
ON chats_chatmessage;

DROP FUNCTION IF EXISTS chats_validate_message_reply();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("chats", "0002_direct_conversation_fields"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_TRIGGERS,
            reverse_sql=DROP_TRIGGERS,
        ),
    ]
