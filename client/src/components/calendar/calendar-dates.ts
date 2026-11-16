import type { CalendarTimelineItem } from "@/lib/api";

export function shiftDay(day: Date, amount: number) {
  const result = new Date(day);
  result.setUTCDate(result.getUTCDate() + amount);
  return result;
}

export function monthDays(month: Date) {
  const start = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth(), 1));
  const monday = shiftDay(start, -((start.getUTCDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, index) => shiftDay(monday, index));
}

export function itemsForDay(items: CalendarTimelineItem[], day: Date) {
  const end = shiftDay(day, 1).getTime();
  return items.filter((item) => Date.parse(item.starts_at) < end && Date.parse(item.ends_at) > day.getTime());
}

export function calendarEventPermissions(workspaceRole: string | null, projectRole: string | null) {
  const admin = workspaceRole === "owner" || workspaceRole === "admin";
  const canDeleteEvent = admin || (workspaceRole !== null && projectRole === "manager");
  const canWrite = canDeleteEvent || (workspaceRole !== null && projectRole === "member");
  return { canCreateEvent: canWrite, canEditEvent: canWrite, canDeleteEvent };
}

export function toggleEventDates(start: string, end: string, allDay: boolean) {
  if (!allDay) return [start + "T09:00", end + "T10:00"] as const;
  const lastDay = end.endsWith("T00:00") && end.slice(0, 10) > start.slice(0, 10)
    ? shiftDay(new Date(end + "Z"), -1).toISOString().slice(0, 10)
    : end.slice(0, 10);
  return [start.slice(0, 10), lastDay] as const;
}
