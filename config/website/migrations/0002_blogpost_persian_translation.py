from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("website", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="blogpost",
            name="title_fa",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="blogpost",
            name="excerpt_fa",
            field=models.CharField(blank=True, max_length=400),
        ),
        migrations.AddField(
            model_name="blogpost",
            name="content_fa",
            field=models.TextField(blank=True, max_length=50000),
        ),
    ]
