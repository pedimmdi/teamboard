
from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION chats_validate_message_reply()
RETURNS trigger AS $$
BEGIN
    IF NEW.reply_to_id IS NOT NULL THEN
        IF NEW.reply_to_id = NEW.id THEN
            RAISE EXCEPTION 'A message cannot reply to itself'
                USING ERRCODE = '23514';
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM chats_chatmessage AS parent
            WHERE parent.id = NEW.reply_to_id
              AND parent.conversation_id = NEW.conversation_id
        ) THEN
            RAISE EXCEPTION
                'Reply must belong to the same conversation'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


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
                'Last read message must belong to the same conversation'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


REVERSE_SQL = FORWARD_SQL.replace(
    " USING ERRCODE = '23514'",
    "",
)


class Migration(migrations.Migration):
    dependencies = [
        ("chats", "0003_chat_integrity"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
        ),
    ]
