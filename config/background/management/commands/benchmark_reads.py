"""Reproducible read benchmarks on disposable, rolled-back fixtures."""
import json
from datetime import timedelta
from statistics import median
from time import perf_counter
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from projects.models import Project, ProjectMembership
from tasks.models import Task
from workspaces.models import Workspace, WorkspaceMembership


class Command(BaseCommand):
    help = "Benchmark unchanged authenticated read endpoints using temporary PostgreSQL fixtures; all fixture rows roll back."
    def add_arguments(self, parser):
        parser.add_argument("--explain", action="store_true")
        parser.add_argument("--tasks", type=int, default=1000)
        parser.add_argument("--projects", type=int, default=10)
        parser.add_argument("--repeats", type=int, default=5)

    def handle(self, *args, **options):
        count, project_count, repeats = options["tasks"], options["projects"], options["repeats"]
        if not 1 <= count <= 20000 or not 1 <= project_count <= 100 or not 1 <= repeats <= 20:
            raise CommandError("Use 1–20000 tasks, 1–100 projects and 1–20 repeats.")
        with transaction.atomic(), override_settings(ALLOWED_HOSTS=["testserver"]):
            actor = get_user_model().objects.create_user(email=f"benchmark-{uuid4().hex}@example.invalid")
            workspace = Workspace.objects.create(name="Temporary benchmark")
            WorkspaceMembership.objects.create(workspace=workspace, user=actor, role="owner")
            projects = []
            for index in range(project_count):
                project = Project.objects.create(workspace=workspace, name=f"Benchmark {index}", created_by=actor)
                ProjectMembership.objects.create(project=project, user=actor, role="manager")
                projects.append(project)
            today = timezone.now().date()
            Task.objects.bulk_create([
                Task(project=projects[index % project_count], assignee=actor, title=f"Task {index}",
                     status=Task.Status.values[index % 4], priority=Task.Priority.values[index % 4],
                     due_date=today + timedelta(days=index % 365))
                for index in range(count)
            ], batch_size=500)
            # Newly inserted, uncommitted fixtures otherwise inherit statistics
            # from the tiny live dataset and produce misleading nested-loop plans.
            benchmark_tables = ("tasks_task", "tasks_taskstatushistory", "projects_project", "projects_projectmembership", "workspaces_workspacemembership")
            with connection.cursor() as cursor:
                for table in benchmark_tables:
                    cursor.execute("ANALYZE " + table)
            client = APIClient()
            client.force_authenticate(actor)
            base = f"/api/v1/workspaces/{workspace.slug}/"
            start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            paths = {
                "projects": (base + "projects/", {}),
                "report_history_90d": (base + "reports/history/", {"period": "90d", "granularity": "day"}),
                "report_workload": (base + "reports/workload/", {}),
                "project_ranking": (base + "reports/projects/", {}),
                "calendar_timeline_7d": (base + "calendar/timeline/", {"start": start.isoformat(), "end": (start + timedelta(days=7)).isoformat()}),
            }
            result = {"fixture_tasks": count, "fixture_projects": project_count, "repeats": repeats, "cache": "disabled", "endpoints": {}}
            for name, (path, query) in paths.items():
                timings, queries = [], []
                for _ in range(repeats):
                    with CaptureQueriesContext(connection) as captured:
                        begin = perf_counter()
                        response = client.get(path, query)
                        timings.append((perf_counter() - begin) * 1000)
                    if response.status_code != 200:
                        raise CommandError(f"{name} returned {response.status_code}; benchmark aborted")
                    queries.append(len(captured))
                result["endpoints"][name] = {"median_ms": round(median(timings), 2), "max_ms": round(max(timings), 2), "queries": max(queries)}
                if options["explain"]:
                    slow = []
                    for query in captured:
                        if float(query["time"]) < 0.05 or not query["sql"].lstrip().upper().startswith("SELECT"):
                            continue
                        with connection.cursor() as cursor:
                            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query["sql"])
                            plan = cursor.fetchone()[0][0]
                        nodes = []
                        def summarize(node):
                            nodes.append({key: node[key] for key in ("Node Type", "Actual Total Time", "Actual Rows", "Actual Loops", "Index Name", "Relation Name") if key in node})
                            for child in node.get("Plans", []):
                                summarize(child)
                        summarize(plan["Plan"])
                        slow.append(nodes)
                    result["endpoints"][name]["slow_plans"] = slow

            transaction.set_rollback(True)
        # Restore planner statistics for the real dataset after fixture rollback.
        with connection.cursor() as cursor:
            for table in benchmark_tables:
                cursor.execute("ANALYZE " + table)
        self.stdout.write(json.dumps(result, indent=2))
