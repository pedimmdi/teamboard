from io import StringIO
import json
from django.core.management import call_command, CommandError
from django.test import TestCase
from workspaces.models import Workspace
from tasks.models import Task

class ReadBenchmarkTests(TestCase):
    def test_benchmark_rolls_back_its_fixture_and_uses_uncached_queries(self):
        before = (Workspace.objects.count(), Task.objects.count())
        output = StringIO()
        call_command("benchmark_reads", tasks=10, projects=2, repeats=1, stdout=output)
        data = json.loads(output.getvalue())
        self.assertEqual(data["cache"], "disabled")
        self.assertEqual(len(data["endpoints"]), 5)
        self.assertTrue(all(item["queries"] > 0 for item in data["endpoints"].values()))
        self.assertEqual(before, (Workspace.objects.count(), Task.objects.count()))

    def test_benchmark_bounds_prevent_unbounded_fixture_creation(self):
        with self.assertRaises(CommandError):
            call_command("benchmark_reads", tasks=20001)

    def test_extended_benchmark_measures_collaboration_endpoints_without_persisting_rows(self):
        from comments.models import Comment
        from chats.models import ChatMessage
        from notifications.models import Notification
        from tasks.models import TaskReminder
        models = (Workspace, Task, Comment, ChatMessage, Notification, TaskReminder)
        before = [model.objects.count() for model in models]
        output = StringIO()
        call_command("benchmark_reads", tasks=10, projects=2, repeats=1, extended=True, stdout=output)
        data = json.loads(output.getvalue())
        self.assertIn("chat_messages", data["endpoints"])
        self.assertIn("dashboard", data["endpoints"])
        self.assertEqual(before, [model.objects.count() for model in models])
