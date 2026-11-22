import type { CalendarTimelineItem } from "@/lib/api";

export function shiftDay(day: Date, amount: number) {
  const result = new Date(day);
  result.setUTCDate(result.getUTCDate() + amount);
  return result;
}

type Calendar = "gregory" | "persian";
const persianDay = new Intl.DateTimeFormat("fa-IR-u-nu-latn", {
  day: "numeric",
  timeZone: "UTC",
});

export function dayOfMonth(date: Date, calendar: Calendar) {
  return calendar === "persian" ? Number(persianDay.format(date)) : date.getUTCDate();
}

export function weekStart(day: Date, firstWeekday = 1) {
  return shiftDay(day, -((day.getUTCDay() - firstWeekday + 7) % 7));
}

export function monthStart(day: Date, calendar: Calendar) {
  return shiftDay(day, 1 - dayOfMonth(day, calendar));
}

export function adjacentMonth(day: Date, direction: number, calendar: Calendar) {
  return monthStart(shiftDay(monthStart(day, calendar), direction > 0 ? 31 : -1), calendar);
}

export function monthDays(month: Date, calendar: Calendar = "gregory", firstWeekday = 1) {
  const start = weekStart(monthStart(month, calendar), firstWeekday);
  return Array.from({ length: 42 }, (_, index) => shiftDay(start, index));
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
