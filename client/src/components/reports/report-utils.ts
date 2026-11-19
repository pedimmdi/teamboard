export function reportDateRange(days: number, today = new Date()) {
  const end = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - days + 1);
  return { start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) };
}

export function validateReportDates(start: string, end: string) {
  const length = (Date.parse(end) - Date.parse(start)) / 86400000;
  return Number.isFinite(length) && length >= 0 && length < 366;
}
