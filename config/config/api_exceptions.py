from django.db import IntegrityError, OperationalError
from django.db.models.deletion import ProtectedError
from rest_framework.response import Response
from rest_framework.views import exception_handler


MANAGER_REQUIRED = "Assign another manager before removing this user from the workspace."


def api_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        return Response({"detail": str(exc.args[0])}, status=409)
    cause = getattr(exc, "__cause__", None)
    constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
    if isinstance(exc, IntegrityError):
        messages = {
            "project_requires_manager": MANAGER_REQUIRED,
            "project_membership_requires_workspace": "Project members must belong to the workspace.",
            "unique_project_membership": "User is already a project member.",
            "unique_project_name_per_workspace": "A project with this name already exists.",
            "valid_project_membership_role": "Invalid project role.",
            "valid_workspace_membership_role": "Invalid workspace role.",
            "project_workspace_immutable": "Moving a project to another workspace is not supported.",
            "project_membership_project_immutable": "Moving a membership to another project is not supported.",
            "project_membership_user_immutable": "Changing a project membership's user is not supported.",
        }
        if constraint in messages:
            return Response({"detail": messages[constraint]}, status=409)
    if isinstance(exc, OperationalError) and getattr(cause, "sqlstate", None) in {"40P01", "40001", "55P03"}:
        return Response({"detail": "Membership changed concurrently. Please retry the request."}, status=409)
    return exception_handler(exc, context)
