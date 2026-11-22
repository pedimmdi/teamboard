from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase

from comments.models import Comment
from comments.services import create_comment
from projects.services import create_project
from tasks.services import create_task
from workspaces.models import Workspace, WorkspaceMembership


class ConcurrentReplyTests(TransactionTestCase):
    def test_two_replies_to_the_same_parent_are_saved(self):
        owner = get_user_model().objects.create_user(email="reply-owner@example.com")
        workspace = Workspace.objects.create(name="Reply workspace")
        WorkspaceMembership.objects.create(workspace=workspace, user=owner, role="owner")
        project = create_project(workspace=workspace, created_by=owner, name="Reply project")
        task = create_task(project=project, actor=owner, title="Reply task")
        parent = create_comment(task=task, actor=owner, body="Parent")
        ready = Barrier(2)

        def reply(body):
            try:
                ready.wait(timeout=10)
                return create_comment(task=task, actor=owner, body=body, reply_to=parent.pk).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = set(pool.map(reply, ("First reply", "Second reply")))
        self.assertEqual(len(ids), 2)
        self.assertEqual(set(Comment.objects.filter(reply_to=parent).values_list("pk", flat=True)), ids)
