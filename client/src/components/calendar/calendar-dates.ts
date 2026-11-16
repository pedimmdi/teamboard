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
