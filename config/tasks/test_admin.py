
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tasks.admin import TaskAdmin
from tasks.models import Task


User = get_user_model()


class TaskAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="task-staff@example.com",
            password="Strong-password-2026!",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

        self.superuser = User.objects.create_superuser(
            email="task-superuser@example.com",
            password="Strong-password-2026!",
        )

    def test_task_is_registered_in_admin(self):
        self.assertIn(Task, admin.site._registry)
        self.assertIsInstance(
            admin.site._registry[Task],
            TaskAdmin,
        )

    def test_staff_can_view_task_list(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin:tasks_task_changelist")
        )

        self.assertEqual(response.status_code, 200)

    def test_staff_cannot_add_task(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin:tasks_task_add")
        )

        self.assertEqual(response.status_code, 403)

    def test_superuser_cannot_add_task(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("admin:tasks_task_add")
        )

        self.assertEqual(response.status_code, 403)

    def test_superuser_cannot_delete_task(self):
        model_admin = admin.site._registry[Task]

        request = self.client.request().wsgi_request
        request.user = self.superuser

        self.assertFalse(
            model_admin.has_delete_permission(request)
        )
        self.assertFalse(
            model_admin.has_change_permission(request)
        )
