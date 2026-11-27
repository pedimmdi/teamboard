from typing import Annotated
from uuid import UUID

from projects.access import get_workspace_project_membership_or_404
from projects.api.v1.serializers import ProjectCreateSerializer, ProjectUpdateSerializer
from projects.models import ProjectMembership
from projects.services import create_project, update_project
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from workspaces.access import get_membership_or_404
from workspaces.api.v1.serializers import WorkspaceSerializer
from workspaces.models import WorkspaceMembership
from workspaces.services import create_workspace

from .tool_schema import WorkspaceSlug

Name = Annotated[StrictStr, Field(min_length=1, max_length=150)]
Description = Annotated[StrictStr, Field(max_length=5000)]
WorkspaceManagers = {WorkspaceMembership.Role.OWNER, WorkspaceMembership.Role.ADMIN}


class WorkspaceWritten(BaseModel):
    workspace_id: UUID
    slug: str


class ProjectWritten(BaseModel):
    project_id: UUID


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    description: Description | None = None


def register_workspace_writes(server, annotations, write, validate):
    @server.tool(annotations=annotations)
    async def teamboard_create_workspace(name: Name, idempotency_key: UUID) -> WorkspaceWritten:
        """Create a workspace owned by your TeamBoard account."""
        def create(user, _):
            space = create_workspace(actor=user, **validate(WorkspaceSerializer, {"name": name}))
            return {"workspace_id": space.pk, "slug": space.slug}

        return WorkspaceWritten(**await write("create_workspace", idempotency_key, {"name": name}, lambda user: user, create))

    @server.tool(annotations=annotations)
    async def teamboard_update_workspace(workspace_slug: WorkspaceSlug, name: Name, idempotency_key: UUID) -> WorkspaceWritten:
        """Rename a workspace you own or administer."""
        def authorize(user):
            return get_membership_or_404(workspace_slug, user, roles=WorkspaceManagers, for_update=True).workspace

        def update(_user, workspace):
            serializer = WorkspaceSerializer(workspace, data={"name": name}, partial=True)
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
            return {"workspace_id": result.pk, "slug": result.slug}

        return WorkspaceWritten(**await write("update_workspace", idempotency_key,
            {"workspace": workspace_slug, "name": name}, authorize, update))

    @server.tool(annotations=annotations)
    async def teamboard_create_project(
        workspace_slug: WorkspaceSlug, name: Name, idempotency_key: UUID, description: Description = "",
    ) -> ProjectWritten:
        """Create a project in a workspace you own or administer."""
        data = {"name": name, "description": description}

        def authorize(user):
            return get_membership_or_404(workspace_slug, user, roles=WorkspaceManagers).workspace

        def create(user, workspace):
            project = create_project(workspace=workspace, created_by=user, **validate(ProjectCreateSerializer, data))
            return {"project_id": project.pk}

        return ProjectWritten(**await write("create_project", idempotency_key,
            {"workspace": workspace_slug, **data}, authorize, create))

    @server.tool(annotations=annotations)
    async def teamboard_update_project(
        workspace_slug: WorkspaceSlug, project_id: UUID, idempotency_key: UUID, changes: ProjectPatch,
    ) -> ProjectWritten:
        """Update the name or description of a project you can manage."""
        data = changes.model_dump(mode="json", exclude_unset=True)

        def authorize(user):
            return get_workspace_project_membership_or_404(workspace_slug=workspace_slug, project_id=project_id,
                user=user, roles={ProjectMembership.Role.MANAGER}).project

        def update(user, project):
            result = update_project(workspace_slug=workspace_slug, project_id=project.pk,
                actor=user, changes=validate(ProjectUpdateSerializer, data))
            return {"project_id": result.pk}

        return ProjectWritten(**await write("update_project", idempotency_key,
            {"workspace": workspace_slug, "project": project_id, **data}, authorize, update))
