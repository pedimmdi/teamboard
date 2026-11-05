import { moveTask, type TaskStatus } from "@/lib/api";

export async function moveTaskToPosition(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  status: TaskStatus,
  beforeId: string | null = null,
  first = false,
) {
  const target = beforeId
    ? { before_task: beforeId }
    : { placement: first ? ("first" as const) : ("last" as const) };
  return moveTask(token, slug, projectId, taskId, status, target);
}
