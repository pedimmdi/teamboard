from unittest.mock import patch

from django.core.cache import cache
from rest_framework.throttling import ScopedRateThrottle

from .test_api import CommentAPIFixture
from .models import Comment
from projects.models import ProjectMembership


class CommentSecurityTests(CommentAPIFixture):
    def test_removed_project_member_cannot_read_comments(self):
        comment = self.make_comment()

        self.authenticate(self.member)
        ProjectMembership.objects.filter(
            project=self.project,
            user=self.member,
        ).delete()

        response = self.client.get(self.detail_url(comment))
        self.assertEqual(response.status_code, 404)

    def test_non_author_cannot_patch_deleted_author_comment(self):
        comment = self.make_comment()
        self.member.delete()

        self.authenticate(self.other_member)
        response = self.client.patch(
            self.detail_url(comment),
            {"body": "Unauthorized"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_comment_not_visible_under_other_task(self):
        comment = self.make_comment()
        self.authenticate(self.member)

        response = self.client.get(
            self.detail_url(comment, task=self.other_task)
        )

        self.assertEqual(response.status_code, 404)

    def test_comment_list_does_not_include_other_task(self):
        self.make_comment(body="Task A")
        Comment.objects.create(
            task=self.other_task,
            author=self.member,
            body="Task B",
        )

        self.authenticate(self.member)
        response = self.client.get(self.list_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["body"],
            "Task A",
        )

    def test_comment_create_throttling(self):
        self.authenticate(self.member)

        with patch.object(
            ScopedRateThrottle,
            "THROTTLE_RATES",
            {"comment_create": "2/min"},
        ):
            cache.clear()

            responses = [
                self.client.post(
                    self.list_url(),
                    {"body": f"Message {i}"},
                    format="json",
                )
                for i in range(3)
            ]

        self.assertEqual(
            [response.status_code for response in responses],
            [201, 201, 429],
        )

        self.assertEqual(
            Comment.objects.filter(task=self.task).count(),
            2,
        )

    def test_removed_author_cannot_modify_own_comment(self):
        comment = self.make_comment()
        original_body = comment.body

        self.authenticate(self.member)

        ProjectMembership.objects.filter(
            project=self.project,
            user=self.member,
        ).delete()

        patch_response = self.client.patch(
            self.detail_url(comment),
            {"body": "Unauthorized update"},
            format="json",
        )

        delete_response = self.client.delete(
            self.detail_url(comment),
        )

        self.assertEqual(patch_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)

        comment.refresh_from_db()
        self.assertEqual(comment.body, original_body)
