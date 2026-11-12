
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from comments.models import Comment
from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()


class CommentAPIFixture(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="comment-owner@example.com",
            password="Strong-password-2026!",
        )
        self.manager = User.objects.create_user(
            email="comment-manager@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="comment-member@example.com",
            password="Strong-password-2026!",
        )
        self.other_member = User.objects.create_user(
            email="comment-other@example.com",
            password="Strong-password-2026!",
        )
        self.workspace_only = User.objects.create_user(
            email="comment-workspace@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="comment-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="Comment Test Workspace",
        )

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.manager, WorkspaceMembership.Role.MEMBER),
            (self.member, WorkspaceMembership.Role.MEMBER),
            (self.other_member, WorkspaceMembership.Role.MEMBER),
            (self.workspace_only, WorkspaceMembership.Role.MEMBER),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        self.project = Project.objects.create(
            workspace=self.workspace,
            name="Comment Test Project",
            created_by=self.owner,
        )

        for user, role in (
            (self.manager, ProjectMembership.Role.MANAGER),
            (self.member, ProjectMembership.Role.MEMBER),
            (self.other_member, ProjectMembership.Role.MEMBER),
        ):
            ProjectMembership.objects.create(
                project=self.project,
                user=user,
                role=role,
            )

        self.task = Task.objects.create(
            project=self.project,
            title="Comment Test Task",
            created_by=self.owner,
        )

        self.other_task = Task.objects.create(
            project=self.project,
            title="Other Task",
            created_by=self.owner,
        )

    def list_url(self, task=None):
        task = task or self.task
        return reverse(
            "workspaces_api_v1:comments_api_v1:comment-list-create",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
            },
        )

    def detail_url(self, comment, task=None):
        task = task or self.task
        return reverse(
            "workspaces_api_v1:comments_api_v1:comment-detail",
            kwargs={
                "slug": self.workspace.slug,
                "project_id": self.project.pk,
                "task_id": task.pk,
                "comment_id": comment.pk,
            },
        )

    def make_comment(self, author=None, body="Hello team"):
        return Comment.objects.create(
            task=self.task,
            author=author or self.member,
            body=body,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)


class CommentAPITests(CommentAPIFixture):
    def test_member_can_create_comment(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.list_url(),
            {"body": "  Hello TeamBoard  "},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )

        comment = Comment.objects.get(
            pk=response.data["id"]
        )

        self.assertEqual(comment.body, "Hello TeamBoard")
        self.assertEqual(comment.author, self.member)
        self.assertEqual(comment.task, self.task)

    def test_member_can_list_comments(self):
        self.make_comment(body="First")
        self.make_comment(body="Second")

        self.authenticate(self.member)

        response = self.client.get(self.list_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            [item["body"] for item in response.data["results"]],
            ["First", "Second"],
        )

    def test_member_can_retrieve_comment(self):
        comment = self.make_comment()

        self.authenticate(self.other_member)

        response = self.client.get(
            self.detail_url(comment)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["id"],
            str(comment.pk),
        )

    def test_author_can_update_comment(self):
        comment = self.make_comment()

        self.authenticate(self.member)

        response = self.client.patch(
            self.detail_url(comment),
            {"body": "Updated comment"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        comment.refresh_from_db()
        self.assertEqual(
            comment.body,
            "Updated comment",
        )

    def test_other_member_cannot_update_comment(self):
        comment = self.make_comment()

        self.authenticate(self.other_member)

        response = self.client.patch(
            self.detail_url(comment),
            {"body": "Unauthorized update"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        comment.refresh_from_db()
        self.assertEqual(comment.body, "Hello team")

    def test_manager_cannot_update_other_users_comment(self):
        comment = self.make_comment()

        self.authenticate(self.manager)

        response = self.client.patch(
            self.detail_url(comment),
            {"body": "Manager update"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_author_can_delete_comment(self):
        comment = self.make_comment()

        self.authenticate(self.member)

        response = self.client.delete(
            self.detail_url(comment)
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Comment.objects.filter(pk=comment.pk).exists()
        )

    def test_manager_can_delete_comment(self):
        comment = self.make_comment()

        self.authenticate(self.manager)

        response = self.client.delete(
            self.detail_url(comment)
        )

        self.assertEqual(response.status_code, 204)

    def test_workspace_owner_can_delete_comment(self):
        comment = self.make_comment()

        self.authenticate(self.owner)

        response = self.client.delete(
            self.detail_url(comment)
        )

        self.assertEqual(response.status_code, 204)

    def test_other_member_cannot_delete_comment(self):
        comment = self.make_comment()

        self.authenticate(self.other_member)

        response = self.client.delete(
            self.detail_url(comment)
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Comment.objects.filter(pk=comment.pk).exists()
        )

    def test_workspace_only_member_cannot_access_comments(self):
        comment = self.make_comment()

        self.authenticate(self.workspace_only)

        responses = [
            self.client.get(self.list_url()),
            self.client.get(self.detail_url(comment)),
            self.client.post(
                self.list_url(),
                {"body": "Unauthorized"},
                format="json",
            ),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                404,
                response.data,
            )

    def test_outsider_cannot_access_comments(self):
        self.authenticate(self.outsider)

        response = self.client.get(self.list_url())

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_cannot_access_comments(self):
        response = self.client.get(self.list_url())

        self.assertIn(
            response.status_code,
            (401, 403),
        )

    def test_comment_cannot_be_accessed_through_other_task(self):
        comment = self.make_comment()

        self.authenticate(self.member)

        response = self.client.get(
            self.detail_url(
                comment,
                task=self.other_task,
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_empty_comment_is_rejected(self):
        self.authenticate(self.member)

        for body in ("", "   "):
            with self.subTest(body=body):
                response = self.client.post(
                    self.list_url(),
                    {"body": body},
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    400,
                    response.data,
                )

        self.assertEqual(Comment.objects.count(), 0)

    def test_comment_over_max_length_is_rejected(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.list_url(),
            {"body": "x" * 5001},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

    def test_author_and_task_cannot_be_overridden(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.list_url(),
            {
                "body": "Protected comment",
                "author_id": self.owner.pk,
                "task": str(self.other_task.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        comment = Comment.objects.get(
            pk=response.data["id"]
        )

        self.assertEqual(comment.author, self.member)
        self.assertEqual(comment.task, self.task)

    def test_comments_are_deleted_with_task(self):
        comment = self.make_comment()
        comment_id = comment.pk

        self.task.delete()

        self.assertFalse(
            Comment.objects.filter(pk=comment_id).exists()
        )

    def test_deleted_author_preserves_comment(self):
        comment = self.make_comment()
        comment_id = comment.pk

        self.member.delete()

        comment = Comment.objects.get(pk=comment_id)

        self.assertIsNone(comment.author)
        self.assertEqual(comment.body, "Hello team")

    def test_pagination(self):
        for index in range(25):
            self.make_comment(body=f"Comment {index}")

        self.authenticate(self.member)

        response = self.client.get(
            self.list_url(),
            {"page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(
            len(response.data["results"]),
            10,
        )
        self.assertIsNotNone(response.data["next"])


class CommentConversationTests(CommentAPIFixture):
    def test_reply_and_mentions_are_scoped_and_edit_updates_mentions(self):
        self.authenticate(self.member)
        parent = self.make_comment()
        response = self.client.post(self.list_url(), {
            "body": f"Thanks @{self.other_member.email}. cc @{self.outsider.email}",
            "reply_to": str(parent.pk),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(str(response.data["reply_to"]), str(parent.pk))
        self.assertEqual(response.data["mentions"], [self.other_member.email])
        reply = Comment.objects.get(pk=response.data["id"])

        changed = self.client.patch(self.detail_url(reply), {"body": "Thanks!"}, format="json")
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(changed.data["mentions"], [])
        self.assertIsNotNone(changed.data["edited_at"])
        parent.delete()
        reply.refresh_from_db()
        self.assertIsNone(reply.reply_to_id)

        rejected = self.client.post(self.list_url(self.other_task), {
            "body": "Reply", "reply_to": str(reply.pk),
        }, format="json")
        self.assertEqual(rejected.status_code, 400, rejected.data)

    def test_file_only_comment_download_requires_task_access(self):
        self.authenticate(self.member)
        upload = SimpleUploadedFile("notes.txt", b"project notes", content_type="text/plain")
        response = self.client.post(self.list_url(), {"attachment": upload}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["attachment"], {"filename": "notes.txt", "size": 13})
        comment = Comment.objects.get(pk=response.data["id"])
        url = self.detail_url(comment) + "attachment/"
        downloaded = self.client.get(url)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(b"".join(downloaded.streaming_content), b"project notes")
        self.assertIn("attachment;", downloaded["Content-Disposition"])
        self.assertEqual(downloaded["Content-Type"], "application/octet-stream")

        self.authenticate(self.workspace_only)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_attachment_limit_rejects_file_and_comment(self):
        self.authenticate(self.member)
        upload = SimpleUploadedFile("large.txt", b"x" * (5 * 1024 * 1024 + 1))
        response = self.client.post(self.list_url(), {"attachment": upload}, format="multipart")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("attachment", response.data)
        self.assertFalse(Comment.objects.filter(task=self.task).exists())

    def test_task_list_returns_per_task_comment_count(self):
        self.make_comment()
        self.make_comment()
        self.authenticate(self.member)
        response = self.client.get(self.list_url().split(f"{self.task.pk}/comments/")[0])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            {str(task["id"]): task["comment_count"] for task in response.data["results"]},
            {str(self.task.pk): 2, str(self.other_task.pk): 0},
        )
