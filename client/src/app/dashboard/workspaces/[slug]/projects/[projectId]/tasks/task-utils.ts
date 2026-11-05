import type {
  Task,
  TaskInput,
  TaskPriority,
  TaskQuery,
  TaskStatus,
} from "@/lib/api";

export const taskStatuses: {
  value: TaskStatus;
  label: string;
  description: string;
}[] = [
  { value: "todo", label: "To Do", description: "Not started yet." },
  {
    value: "in_progress",
    label: "In Progress",
    description: "Someone is working on it.",
  },
  {
    value: "in_review",
    label: "In Review",
    description: "Waiting for review.",
  },
  { value: "done", label: "Done", description: "Finished." },
];
export const taskPriorities: TaskPriority[] = [
  "low",
  "medium",
  "high",
  "urgent",
];
export const taskOrderings = [
  "due_date",
  "-due_date",
  "-created_at",
  "created_at",
  "-updated_at",
  "title",
  "-title",
  "priority",
  "-priority",
  "status",
  "-status",
] as const;
export type TaskFilters = {
  search: string;
  statuses: TaskStatus[];
  priority: TaskPriority | "";
  assignee: string;
  ordering: (typeof taskOrderings)[number];
  overdue: boolean;
  dueBefore: string;
};
export const emptyTaskFilters: TaskFilters = {
  search: "",
  statuses: [],
  priority: "",
  assignee: "",
  ordering: "due_date",
  overdue: false,
  dueBefore: "",
};

export function readTaskFilters(
  params: Pick<URLSearchParams, "get">,
): TaskFilters {
  const priority = params.get("priority");
  const assignee = params.get("assignee") || "";
  const ordering = params.get("ordering");
  const dueBefore = params.get("due_before") || "";
  return {
    search: (params.get("search") || "").slice(0, 200),
    statuses: [
      ...new Set(
        (params.get("status") || "")
          .split(",")
          .filter((value): value is TaskStatus =>
            taskStatuses.some((status) => status.value === value),
          ),
      ),
    ],
    priority: taskPriorities.includes(priority as TaskPriority)
      ? (priority as TaskPriority)
      : "",
    assignee:
      params.get("unassigned") === "true"
        ? "unassigned"
        : assignee === "me" || /^[1-9]\d*$/.test(assignee)
          ? assignee
          : "",
    ordering: taskOrderings.includes(ordering as (typeof taskOrderings)[number])
      ? (ordering as (typeof taskOrderings)[number])
      : "due_date",
    overdue: params.get("overdue") === "true",
    dueBefore: validDate(dueBefore) ? dueBefore : "",
  };
}
export function validDate(value: string) {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(value)) &&
    new Date(value).toISOString().slice(0, 10) === value
  );
}
export function taskFilterQuery(filters: TaskFilters): TaskQuery {
  return {
    search: filters.search.trim() || undefined,
    status: filters.statuses.length ? filters.statuses : undefined,
    priority: filters.priority || undefined,
    assignee:
      filters.assignee === "me"
        ? "me"
        : /^[1-9]\d*$/.test(filters.assignee)
          ? Number(filters.assignee)
          : undefined,
    unassigned: filters.assignee === "unassigned" ? true : undefined,
    ordering: filters.ordering,
    overdue: filters.overdue || undefined,
    due_before: filters.dueBefore || undefined,
  };
}
export function writeTaskFilters(
  filters: TaskFilters,
  params = new URLSearchParams(),
) {
  for (const key of [
    "search",
    "status",
    "priority",
    "assignee",
    "unassigned",
    "ordering",
    "overdue",
    "due_before",
    "page",
  ])
    params.delete(key);
  for (const [key, value] of Object.entries(taskFilterQuery(filters))) {
    if (value !== undefined)
      params.set(key, Array.isArray(value) ? value.join(",") : String(value));
  }
  return params;
}
export function hasTaskFilters(filters: TaskFilters) {
  return Boolean(
    filters.search.trim() ||
      filters.statuses.length ||
      filters.priority ||
      filters.assignee ||
      filters.overdue ||
      filters.dueBefore,
  );
}
export function overdueDays(
  dueDate: string | null,
  status: TaskStatus,
  today = new Date(),
) {
  if (!dueDate || status === "done") return 0;
  const start = Date.UTC(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );
  return Math.max(
    0,
    Math.floor((start - Date.parse(`${dueDate}T00:00:00Z`)) / 86400000),
  );
}
export function taskDate(value: string, withYear = false) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    ...(withYear ? { year: "numeric" } : {}),
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
export function taskInput(task?: Task, status: TaskStatus = "todo"): TaskInput {
  return task
    ? {
        title: task.title,
        description: task.description,
        status: task.status,
        priority: task.priority,
        assignee: task.assignee,
        due_date: task.due_date,
      }
    : {
        title: "",
        description: "",
        status,
        priority: "medium",
        assignee: null,
        due_date: null,
      };
}
export function taskChanges(
  initial: TaskInput,
  next: TaskInput,
): Partial<TaskInput> {
  return Object.fromEntries(
    Object.entries(next).filter(
      ([key, value]) => value !== initial[key as keyof TaskInput],
    ),
  );
}
// Positions belong to the complete server column, even when some cards are filtered out.
export function taskMovePosition(
  task: Pick<Task, "id" | "status" | "position">,
  status: TaskStatus,
  before: Pick<Task, "id" | "position"> | null,
  destinationCount: number,
) {
  if (before?.id === task.id) return task.position;
  if (before)
    return Math.max(
      0,
      before.position -
        (task.status === status && task.position < before.position ? 1 : 0),
    );
  return Math.max(0, destinationCount - (task.status === status ? 1 : 0));
}
