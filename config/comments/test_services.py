
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from comments.models import Comment
from comments.services import (
    create_comment,
    update_comment,
    delete_comment,
    validate_comment_body,
)
from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


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
