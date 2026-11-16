"use client";

import CalendarView from "@/components/calendar/calendar-view";
import { useWorkspace } from "../../../workspace-context";
import { projectPermissions } from "../../project-utils";
import { useProjectContext } from "../project-context";

export default function ProjectCalendarPage() {
  const workspace = useWorkspace();
  const { project } = useProjectContext();
  const { canManage } = projectPermissions(workspace.role, project.role);
  return <CalendarView slug={workspace.slug} projectId={project.id} canManage={canManage} />;
}
