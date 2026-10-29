from django.db import migrations


def move_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    alias = schema_editor.connection.alias
    for suffix in ('', 'membership', 'invitation'):
        old_model = f'organization{suffix}'
        new_model = f'workspace{suffix}'
        content_type = ContentType.objects.using(alias).filter(
            app_label='organizations', model=old_model,
        ).first()
        if content_type is None:
            continue
        content_type.app_label = 'workspaces'
        content_type.model = new_model
        content_type.save(using=alias, update_fields=['app_label', 'model'])
        for permission in Permission.objects.using(alias).filter(content_type=content_type):
            permission.codename = permission.codename.replace(old_model, new_model)
            permission.name = permission.name.replace('organization', 'workspace')
            permission.save(using=alias, update_fields=['codename', 'name'])


class Migration(migrations.Migration):
    dependencies = [
        ('workspaces', '0003_rename_org_inv_email_status_idx_ws_inv_email_status_idx_and_more'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [migrations.RunPython(move_content_types, migrations.RunPython.noop)]
