
from django.contrib import admin
from django.test import SimpleTestCase

from comments.admin import CommentAdmin
from comments.models import Comment


class CommentAdminTests(SimpleTestCase):
    def test_comment_is_registered_in_admin(self):
        self.assertIn(Comment, admin.site._registry)

    def test_comment_admin_configuration(self):
        model_admin = admin.site._registry[Comment]

        self.assertIsInstance(model_admin, CommentAdmin)

        self.assertEqual(
            model_admin.list_per_page,
            25,
        )

        self.assertIn(
            "task",
            model_admin.autocomplete_fields,
        )

        self.assertIn(
            "author",
            model_admin.autocomplete_fields,
        )

    def test_body_preview_truncates_long_text(self):
        model_admin = admin.site._registry[Comment]

        comment = Comment(body="A" * 100)

        preview = model_admin.body_preview(comment)

        self.assertEqual(
            preview,
            "A" * 80 + "...",
        )

    def test_body_preview_preserves_short_text(self):
        model_admin = admin.site._registry[Comment]

        comment = Comment(body="Hello TeamBoard")

        self.assertEqual(
            model_admin.body_preview(comment),
            "Hello TeamBoard",
        )
