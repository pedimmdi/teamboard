const interactionId = "[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}";
const consentHash = new RegExp(`^#interaction=(${interactionId})$`);
const loginHash = new RegExp(`^#ai=(${interactionId})$`);
const approvalHash = new RegExp(`^#approval=(${interactionId})$`);
const approvalLoginHash = new RegExp(`^#approve-task=(${interactionId})$`);

export function getAiConsentInteraction(hash: string) {
  return consentHash.exec(hash)?.[1] ?? null;
}

export function getAiConsentReturn(hash: string) {
  const id = loginHash.exec(hash)?.[1];
  if (id) return `/ai/authorize#interaction=${id}`;
  const approval = approvalLoginHash.exec(hash)?.[1];
  return approval ? `/ai/approve-task-deletion#approval=${approval}` : null;
}

export function getTaskDeletionApproval(hash: string) {
  return approvalHash.exec(hash)?.[1] ?? null;
}

export function getLocalAiCallback(value: string) {
  try {
    const url = new URL(value);
    if (url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) &&
        url.port && !url.username && !url.password && !url.hash) return url.href;
  } catch {
    return null;
  }
  return null;
}

export function getAiCallback(value: string, registered: string) {
  try {
    const target = new URL(value);
    const expected = new URL(registered);
    if (target.origin !== expected.origin || target.pathname !== expected.pathname ||
        target.username || target.password || target.hash || expected.username || expected.password || expected.hash ||
        [...expected.searchParams].some(([key, val]) => !target.searchParams.getAll(key).includes(val))) return null;
    return target.protocol === "https:" && !target.port ? target.href : getLocalAiCallback(value);
  } catch {
    return null;
  }
}
