from django.db import migrations


def backfill_task_positions(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    db_alias = schema_editor.connection.alias

    tasks = Task.objects.using(db_alias).order_by(
        "project_id",
        "status",
        "created_at",
        "pk",
    )

    current_group = None
    next_position = 0
    batch = []

    for task in tasks.iterator(chunk_size=1000):
        group = (task.project_id, task.status)

        if group != current_group:
            current_group = group
            next_position = 0

        task.position = next_position
        next_position += 1
        batch.append(task)

        if len(batch) >= 1000:
            Task.objects.using(db_alias).bulk_update(
                batch,
                ["position"],
                batch_size=1000,
            )
            batch.clear()

    if batch:
        Task.objects.using(db_alias).bulk_update(
            batch,
            ["position"],
            batch_size=1000,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0004_task_position"),
    ]

    operations = [
        migrations.RunPython(
            backfill_task_positions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]