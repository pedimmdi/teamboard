from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("background", "0002_backgroundjob_dispatched_at")]

    operations = [
        migrations.AlterField(
            model_name="backgroundjob",
            name="kind",
            field=models.CharField(
                choices=[
                    ("email", "Email"),
                    ("comment_file", "Comment file deletion"),
                    ("chat_attachment", "Deleted chat attachment"),
                    ("avatar_file", "Avatar file deletion"),
                ],
                max_length=24,
            ),
        ),
    ]
