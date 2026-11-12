from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import migrations, models


def move_files(apps, schema_editor):
    attachments = apps.get_model("comments", "CommentAttachment").objects.using(schema_editor.connection.alias)
    storage = FileSystemStorage(location=settings.COMMENT_ATTACHMENT_ROOT, file_permissions_mode=0o600)
    for attachment in attachments.iterator(chunk_size=16):
        key = f"legacy/{attachment.comment_id.hex}"
        data = bytes(attachment.content)
        if storage.exists(key):
            with storage.open(key, "rb") as existing:
                if existing.read() != data:
                    raise RuntimeError(f"Attachment storage conflict at {key}")
        else:
            key = storage.save(key, ContentFile(data))
        attachments.filter(pk=attachment.pk).update(storage_key=key)


def restore_files(apps, schema_editor):
    attachments = apps.get_model("comments", "CommentAttachment").objects.using(schema_editor.connection.alias)
    storage = FileSystemStorage(location=settings.COMMENT_ATTACHMENT_ROOT)
    for attachment in attachments.iterator(chunk_size=16):
        with storage.open(attachment.storage_key, "rb") as file:
            attachments.filter(pk=attachment.pk).update(content=file.read())


class Migration(migrations.Migration):
    dependencies = [("comments", "0002_comment_edited_at_comment_mentions_comment_reply_to_and_more")]
    operations = [
        migrations.AddField(
            model_name="commentattachment", name="storage_key",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="commentattachment", name="content",
            field=models.BinaryField(null=True),
        ),
        migrations.RunPython(move_files, restore_files),
        migrations.AlterField(
            model_name="commentattachment", name="storage_key",
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.RemoveField(model_name="commentattachment", name="content"),
    ]
