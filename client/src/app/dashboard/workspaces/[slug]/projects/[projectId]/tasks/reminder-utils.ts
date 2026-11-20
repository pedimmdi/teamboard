function parts(value: Date, zone: string) {
  const result = new Intl.DateTimeFormat("en-CA", {timeZone: zone, year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(value);
  const get = (type: string) => result.find((part) => part.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}
export function reminderLocalInput(iso: string, zone: string) {return parts(new Date(iso), zone);}
export function reminderLocalToUTC(input: string, zone: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(input)) throw new Error("Choose a valid local date and time.");
  const seed = Date.parse(input + "Z");
  if (!Number.isFinite(seed)) throw new Error("Choose a valid local date and time.");
  const matches = new Set<string>();
  // Contemporary IANA offsets are multiples of 15 minutes. Enumerating possible
  // offsets detects gaps and folds instead of silently shifting local times.
  for (let offset = -14 * 60; offset <= 14 * 60; offset += 15) {
    const candidate = new Date(seed - offset * 60_000);
    if (parts(candidate, zone) === input) matches.add(candidate.toISOString());
  }
  if (matches.size !== 1) throw new Error("This local time is ambiguous or does not exist. Choose another time or select UTC.");
  return [...matches][0];
}
export function futureReminderTime(input: string, zone: string) {
  const iso = reminderLocalToUTC(input, zone);
  if (Date.parse(iso) <= Date.now()) throw new Error("Choose a future reminder time.");
  return iso;
}
