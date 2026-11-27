import uuid

from django.conf import settings
from django.db import models


class AuthorizationInteraction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    browser_digest = models.CharField(max_length=64)
    client_id = models.CharField(max_length=100)
    credentials = models.JSONField()
    expires_at = models.DateTimeField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, editable=False
    )


class MutationReceipt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_id = models.CharField(max_length=100)
    tool = models.CharField(max_length=64)
    key = models.UUIDField()
    input_digest = models.CharField(max_length=64)
    result = models.JSONField()
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("user", "client_id", "tool", "key"), name="mcp_mutation_receipt_unique",
        )]


class TaskDeletionApproval(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_id = models.CharField(max_length=100)
    workspace_slug = models.CharField(max_length=10)
    project_id = models.UUIDField()
    task_id = models.UUIDField()
    task_title = models.CharField(max_length=200)
    task_version = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    decided_at = models.DateTimeField(null=True)
    approved = models.BooleanField(null=True)
