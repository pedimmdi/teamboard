export function createTimedReadCache<T>(ttlMs: number, maxEntries: number) {
  const entries = new Map<string, { value: T; expiresAt: number }>();
  const pending = new Map<string, Promise<T>>();

  return async function read(key: string, load: () => Promise<T>): Promise<T> {
    const entry = entries.get(key);
    if (entry && entry.expiresAt > Date.now()) return entry.value;
    entries.delete(key);

    const active = pending.get(key);
    if (active) return active;
    if (pending.size >= maxEntries) return load();

    const request = Promise.resolve().then(load).then((value) => {
      if (entries.size >= maxEntries) {
        const oldest = entries.keys().next().value;
        if (oldest !== undefined) entries.delete(oldest);
      }
      entries.set(key, { value, expiresAt: Date.now() + ttlMs });
      return value;
    }).finally(() => pending.delete(key));

    pending.set(key, request);
    return request;
  };
}

export function createSitemapReader<T>(load: () => Promise<T>, fallback: T) {
  const freshForMs = 5 * 60_000;
  const maxAgeMs = 60 * 60_000;
  const retryAfterMs = 15_000;
  let snapshot: { value: T; loadedAt: number } | undefined;
  let nextRefresh = 0;
  let active: Promise<void> | undefined;

  return async function read(): Promise<T> {
    if (Date.now() >= nextRefresh) {
      active ??= Promise.resolve().then(load).then((value) => {
        const loadedAt = Date.now();
        snapshot = { value, loadedAt };
        nextRefresh = loadedAt + freshForMs;
      }).catch(() => {
        nextRefresh = Date.now() + retryAfterMs;
      }).finally(() => { active = undefined; });
      await active;
    }
    return snapshot && Date.now() - snapshot.loadedAt < maxAgeMs ? snapshot.value : fallback;
  };
}
