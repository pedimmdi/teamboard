export const IRAN_TIME_ZONE = "Asia/Tehran";

const civilFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: IRAN_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function iranWallClock(value: string | Date) {
  const parts = civilFormatter.formatToParts(new Date(value));
  const part = (key: Intl.DateTimeFormatPartTypes) => parts.find(({ type }) => type === key)?.value;
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
}

function candidateInstants(input: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(input)) return [];
  const nominal = Date.parse(`${input}:00Z`);
  if (!Number.isFinite(nominal) || new Date(nominal).toISOString().slice(0, 16) !== input) return [];
  // Sample on both sides so a past clock change can produce both possible offsets.
  const candidates = [-86_400_000, 0, 86_400_000].map((delta) => {
    const sample = nominal + delta;
    const offset = Date.parse(`${iranWallClock(new Date(sample))}:00Z`) - sample;
    return nominal - offset;
  });
  return [...new Set(candidates)].sort((a, b) => a - b).map((time) => new Date(time));
}

export function iranInstant(input: string): Date | null {
  const matching = candidateInstants(input).filter((candidate) => iranWallClock(candidate) === input);
  return matching.length === 1 ? matching[0] : null;
}

export function iranDayBoundary(day: Date) {
  const key = day.toISOString().slice(0, 10);
  const midnight = `${key}T00:00`;
  // On historical midnight clock changes, use the earliest instant in the civil day.
  return candidateInstants(midnight).find((candidate) => iranWallClock(candidate).startsWith(key)) ?? day;
}

export function iranCivilDay(now: Date) {
  return new Date(`${iranWallClock(now).slice(0, 10)}T00:00:00Z`);
}
