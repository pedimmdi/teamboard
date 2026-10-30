from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from django.utils import timezone


class WorkspaceUpgradeTests(TransactionTestCase):
    """Exercise the same recorded history and tables as the former app."""

    def test_existing_database_keeps_rows_and_permissions(self):
        first = ('workspaces', '0001_legacy_replacement')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [
            node
            for node in latest
            if node[0] not in ("workspaces", "projects")
        ] + [first]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            User = apps.get_model('accounts', 'User')
            user = User.objects.create(email='upgrade@example.com', password='unused')
            workspace = apps.get_model('workspaces', 'Organization').objects.create(name='Existing team')
            membership = apps.get_model('workspaces', 'OrganizationMembership').objects.create(
                organization=workspace, user=user, role='owner',
            )
            invitation = apps.get_model('workspaces', 'OrganizationInvitation').objects.create(
                organization=workspace, invited_by=user, email='invited@example.com',
                token_hash='a' * 64, expires_at=timezone.now() + timedelta(days=7),
            )
            ContentType = apps.get_model('contenttypes', 'ContentType')
            Permission = apps.get_model('auth', 'Permission')
            ContentType.objects.filter(app_label='workspaces').delete()
            content_type = ContentType.objects.create(app_label='organizations', model='organization')
            permission = Permission.objects.create(
                content_type=content_type, codename='change_organization', name='Can change organization',
            )
            user.user_permissions.add(permission)

            recorder = MigrationRecorder(connection)
            recorder.record_unapplied(*first)
            for name in (
                '0001_initial', '0002_organizationmembership_unique_organization_owner',
                '0003_organizationinvitation',
            ):
                recorder.record_applied('organizations', name)

            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            self.assertEqual(apps.get_model('workspaces', 'Workspace').objects.get(pk=workspace.pk).slug, workspace.slug)
            self.assertEqual(apps.get_model('workspaces', 'WorkspaceMembership').objects.get(pk=membership.pk).workspace_id, workspace.pk)
            self.assertEqual(apps.get_model('workspaces', 'WorkspaceInvitation').objects.get(pk=invitation.pk).token_hash, 'a' * 64)
            moved = apps.get_model('auth', 'Permission').objects.get(pk=permission.pk)
            self.assertEqual(moved.codename, 'change_workspace')
            self.assertEqual(moved.content_type_id, content_type.pk)
            self.assertTrue(user.user_permissions.filter(pk=permission.pk).exists())
            self.assertFalse(any(table.startswith('organizations_') for table in connection.introspection.table_names()))
        finally:
            MigrationExecutor(connection).migrate(latest)
