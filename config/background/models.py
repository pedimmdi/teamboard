import uuid
from django.db import models
from django.utils import timezone

class BackgroundJob(models.Model):
    """Durable outbox. Broker messages contain only this record's UUID."""
    class Kind(models.TextChoices):
        EMAIL = "email", "Email"
        COMMENT_FILE = "comment_file", "Comment file deletion"
        CHAT_ATTACHMENT = "chat_attachment", "Deleted chat attachment"
        AVATAR_FILE = "avatar_file", "Avatar file deletion"
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    payload = models.JSONField(default=dict)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    last_error = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=["state", "available_at"], name="background_pending_idx")]
