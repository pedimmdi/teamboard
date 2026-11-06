
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .test_api import CommentAPIFixture
from .models import Comment


class CommentPerformanceTests(CommentAPIFixture):
    def test_comment_list_query_count_does_not_grow(self):
        self.authenticate(self.member)

        Comment.objects.create(
            task=self.task,
            author=self.member,
            body="First comment",
        )

        with CaptureQueriesContext(connection) as queries_one:
            response_one = self.client.get(self.list_url())

        self.assertEqual(response_one.status_code, 200)
        self.assertEqual(response_one.data["count"], 1)

        for i in range(19):
            Comment.objects.create(
                task=self.task,
                author=self.member,
                body=f"Additional comment {i}",
            )

        with CaptureQueriesContext(connection) as queries_many:
            response_many = self.client.get(self.list_url())

        self.assertEqual(response_many.status_code, 200)
        self.assertEqual(response_many.data["count"], 20)

        count_one = len(queries_one)
        count_many = len(queries_many)

        self.assertLessEqual(
            count_many,
            count_one + 1,
            (
                "Possible N+1 query detected: "
                f"1 comment = {count_one} queries, "
                f"20 comments = {count_many} queries"
            ),
        )
