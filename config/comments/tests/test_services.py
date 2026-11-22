from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)
from comments.models import Comment, CommentAttachment
from comments.services import (
    create_comment,
    update_comment,
    delete_comment,
    validate_comment_body,
)
from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership
from notifications.models import Notification


User = get_user_model()


class CommentServiceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="service-author@example.com",
            password="Strong-password-2026!",
        )
        self.other = User.objects.create_user(
            email="service-other@example.com",
            password="Strong-password-2026!",
        )

        # 1. Create workspace
        self.workspace = Workspace.objects.create(
            name="Comment Service Workspace",
        )

        # 2. Create workspace memberships
        for user in (self.author, self.other):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=WorkspaceMembership.Role.MEMBER,
            )

        # 3. Create project
        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Comment Service Project",
            created_by=self.author,
        )

        # 4. Create project memberships
        ProjectMembership.objects.create(
            project=self.project,
            user=self.author,
            role=ProjectMembership.Role.MANAGER,
        )

        ProjectMembership.objects.create(
            project=self.project,
            user=self.other,
            role=ProjectMembership.Role.MEMBER,
        )

        # 5. Create task
        self.task = Task.objects.create(
            project=self.project,
            title="Service Test Task",
            created_by=self.author,
        )

    def test_create_comment(self):
        comment = create_comment(
            task=self.task,
            actor=self.author,
            body="  New comment  ",
        )

        self.assertEqual(comment.body, "New comment")
        self.assertEqual(comment.author, self.author)

    def test_update_comment(self):
        comment = create_comment(
            task=self.task,
            actor=self.author,
            body="Original",
        )

        updated = update_comment(
            comment=comment,
            actor=self.author,
            body="Updated",
        )

        self.assertEqual(updated.body, "Updated")

    def test_other_user_cannot_update(self):
        comment = Comment.objects.create(
            task=self.task,
            author=self.author,
            body="Original",
        )

        with self.assertRaises(PermissionDenied):
            update_comment(
                comment=comment,
                actor=self.other,
                body="Unauthorized",
            )

    def test_author_can_delete(self):
        comment = Comment.objects.create(
            task=self.task,
            author=self.author,
            body="Delete me",
        )

        delete_comment(
            comment=comment,
            actor=self.author,
        )

        self.assertFalse(
            Comment.objects.filter(pk=comment.pk).exists()
        )

    def test_other_member_cannot_delete(self):
        comment = Comment.objects.create(
            task=self.task,
            author=self.author,
            body="Protected",
        )

        with self.assertRaises(PermissionDenied):
            delete_comment(
                comment=comment,
                actor=self.other,
            )

        self.assertTrue(
            Comment.objects.filter(pk=comment.pk).exists()
        )

    def test_validation_rejects_invalid_bodies(self):
        for body in ("", "  ", None, 123, "x" * 5001):
            with self.subTest(body=body):
                with self.assertRaises(ValidationError):
                    validate_comment_body(body)

    def test_validation_trims_body(self):
        self.assertEqual(
            validate_comment_body("  Hello  "),
            "Hello",
        )

    def test_create_comment_with_mention_notifies_user(self):
        comment = create_comment(
            task=self.task,
            actor=self.author,
            body=f"Please review @{self.other.email}",
        )

        notification = Notification.objects.get()

        self.assertEqual(
            notification.event_type,
            Notification.EventType.COMMENT_MENTIONED,
        )
        self.assertEqual(notification.recipient_id, self.other.pk)
        self.assertEqual(notification.actor_id, self.author.pk)
        self.assertEqual(notification.workspace_id, self.workspace.pk)
        self.assertEqual(notification.project_id, self.project.pk)
        self.assertEqual(notification.task_id, self.task.pk)
        self.assertEqual(
            notification.payload,
            {"comment_id": str(comment.pk)},
        )

    def test_duplicate_mentions_create_one_notification(self):
        create_comment(
            task=self.task,
            actor=self.author,
            body=f"@{self.other.email} and @{self.other.email}",
        )

        self.assertEqual(Notification.objects.count(), 1)

    def test_self_mention_creates_no_notification(self):
        create_comment(
            task=self.task,
            actor=self.author,
            body=f"Hello @{self.author.email}",
        )

        self.assertFalse(Notification.objects.exists())

    def test_reply_notifies_parent_author(self):
        parent = create_comment(
            task=self.task,
            actor=self.other,
            body="Original comment",
        )

        reply = create_comment(
            task=self.task,
            actor=self.author,
            body="My reply",
            reply_to=parent.pk,
        )

        notification = Notification.objects.get()

        self.assertEqual(
            notification.event_type,
            Notification.EventType.COMMENT_REPLIED,
        )
        self.assertEqual(notification.recipient_id, self.other.pk)
        self.assertEqual(
            notification.payload,
            {
                "comment_id": str(reply.pk),
                "parent_comment_id": str(parent.pk),
            },
        )

    def test_reply_to_own_comment_does_not_notify(self):
        parent = create_comment(
            task=self.task,
            actor=self.author,
            body="My comment",
        )

        create_comment(
            task=self.task,
            actor=self.author,
            body="My reply",
            reply_to=parent.pk,
        )

        self.assertFalse(Notification.objects.exists())

    def test_reply_mentioning_parent_author_creates_one_notification(self):
        parent = create_comment(
            task=self.task,
            actor=self.other,
            body="Original",
        )

        create_comment(
            task=self.task,
            actor=self.author,
            body=f"Reply @{self.other.email}",
            reply_to=parent.pk,
        )

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(
            Notification.objects.get().event_type,
            Notification.EventType.COMMENT_REPLIED,
        )

    def test_edit_adds_new_mention_notification(self):
        comment = create_comment(
            task=self.task,
            actor=self.author,
            body="Original text",
        )

        update_comment(
            comment=comment,
            actor=self.author,
            body=f"Updated @{self.other.email}",
        )

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(
            Notification.objects.get().event_type,
            Notification.EventType.COMMENT_MENTIONED,
        )

    def test_edit_existing_mention_does_not_notify_again(self):
        comment = create_comment(
            task=self.task,
            actor=self.author,
            body=f"Hello @{self.other.email}",
        )

        update_comment(
            comment=comment,
            actor=self.author,
            body=f"Updated text @{self.other.email}",
        )

        self.assertEqual(Notification.objects.count(), 1)

    def test_edit_without_new_mentions_does_not_notify(self):
        comment = create_comment(
            task=self.task,
            actor=self.author,
            body="Original",
        )

        update_comment(
            comment=comment,
            actor=self.author,
            body="Updated",
        )

        self.assertFalse(Notification.objects.exists())

    def test_notification_failure_rolls_back_comment_creation(self):
        with patch(
            "comments.services.notify_comment_mentioned",
            side_effect=RuntimeError("Notification failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Notification failure",
            ):
                create_comment(
                    task=self.task,
                    actor=self.author,
                    body=f"Rollback @{self.other.email}",
                )

        self.assertFalse(Comment.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_notification_failure_rolls_back_comment_edit(self):
        comment = create_comment(
            task=self.task,
            actor=self.author,
            body="Original",
        )

        with patch(
            "comments.services.notify_comment_mentioned",
            side_effect=RuntimeError("Notification failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Notification failure",
            ):
                update_comment(
                    comment=comment,
                    actor=self.author,
                    body=f"Updated @{self.other.email}",
                )

        comment.refresh_from_db()
        self.assertEqual(comment.body, "Original")
        self.assertFalse(Notification.objects.exists())

    def test_attachment_is_deleted_when_notification_fails(self):
        attachment = SimpleUploadedFile(
            "test.txt",
            b"Safe attachment content",
            content_type="text/plain",
        )

        with patch("comments.services.attachment_storage") as storage_factory:
            storage = storage_factory.return_value
            storage.save.return_value = "uploads/test-file-key"

            with patch(
                "comments.services.notify_comment_mentioned",
                side_effect=RuntimeError("Notification failure"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "Notification failure",
                ):
                    create_comment(
                        task=self.task,
                        actor=self.author,
                        body=f"Review @{self.other.email}",
                        attachment=attachment,
                    )

            storage.delete.assert_called_once_with(
                "uploads/test-file-key",
            )

        self.assertFalse(Comment.objects.exists())
        self.assertFalse(CommentAttachment.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_mention_without_workspace_membership_is_not_notified(self):
        self.other.workspace_memberships.filter(
            workspace=self.workspace,
        ).delete()

        create_comment(
            task=self.task,
            actor=self.author,
            body=f"Review @{self.other.email}",
        )

        self.assertFalse(
            Notification.objects.filter(
                recipient=self.other,
                event_type=Notification.EventType.COMMENT_MENTIONED,
            ).exists()
        )
