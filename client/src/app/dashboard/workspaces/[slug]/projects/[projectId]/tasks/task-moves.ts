import { getTask, getTasks, moveTask, type TaskStatus } from "@/lib/api";
import { taskMovePosition } from "./task-utils";

export async function moveTaskToPosition(
  token: string,
  slug: string,
  projectId: string,
  taskId: string,
  status: TaskStatus,
  beforeId: string | null = null,
  first = false,
) {
  const [task, before, column] = await Promise.all([
    getTask(token, slug, projectId, taskId),
    beforeId ? getTask(token, slug, projectId, beforeId) : null,
    !beforeId && !first
      ? getTasks(token, slug, projectId, { status: [status], page_size: 1 })
      : null,
  ]);
  if (before && before.status !== status) {
    throw new Error("The destination task moved. Please try again.");
  }
  const position = first
    ? 0
    : taskMovePosition(task, status, before, column?.count || 0);
  return moveTask(token, slug, projectId, taskId, status, position);
}
