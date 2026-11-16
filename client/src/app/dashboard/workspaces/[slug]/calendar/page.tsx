"use client";

import CalendarView from "@/components/calendar/calendar-view";
import { useWorkspace } from "../workspace-context";

export default function WorkspaceCalendarPage() {
  const { slug } = useWorkspace();
  return <CalendarView slug={slug} canCreateEvent />;
}
