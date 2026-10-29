from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('workspaces', '0001_legacy_replacement')]
    operations = [
        migrations.RenameModel('Organization', 'Workspace'),
        migrations.RenameModel('OrganizationMembership', 'WorkspaceMembership'),
        migrations.RenameModel('OrganizationInvitation', 'WorkspaceInvitation'),
        migrations.RemoveConstraint('workspacemembership', 'unique_organization_membership'),
        migrations.RemoveConstraint('workspacemembership', 'unique_organization_owner'),
        migrations.RemoveConstraint('workspaceinvitation', 'unique_pending_org_invitation_email'),
        migrations.RemoveIndex('workspaceinvitation', 'org_inv_status_idx'),
        migrations.RenameField('workspacemembership', 'organization', 'workspace'),
        migrations.RenameField('workspaceinvitation', 'organization', 'workspace'),
    ]
