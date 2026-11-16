"use client";

import CalendarView from "@/components/calendar/calendar-view";
import { useWorkspace } from "../../../workspace-context";
import { calendarEventPermissions } from "@/components/calendar/calendar-dates";
import { useProjectContext } from "../project-context";

export default function ProjectCalendarPage() {
  const workspace = useWorkspace();
  const { project } = useProjectContext();
  const permissions = calendarEventPermissions(workspace.role, project.role);
  return <CalendarView slug={workspace.slug} projectId={project.id} {...permissions} />;
}
