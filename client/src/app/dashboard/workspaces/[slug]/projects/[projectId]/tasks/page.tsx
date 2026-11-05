"use client";

import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ApiError,
  createTask,
  deleteTask,
  getProjectMembers,
  getTasks,
  type PaginatedTasks,
  type ProjectMember,
  type Task,
  type TaskQuery,
  type TaskStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import Avatar from "@/components/ui/Avatar";
import { useWorkspace } from "../../../workspace-context";
import { useProjectContext } from "../project-context";
import { projectPermissions } from "../../project-utils";
import AssigneePicker from "./assignee-picker";
import TaskActions from "./task-actions";
import TaskDialog from "./task-dialog";
import TaskDrawer from "./task-drawer";
import TaskForm from "./task-form";
import TaskFiltersDialog, { orderingLabels } from "./task-filters";
import TaskIcon from "./task-icons";
import {
  emptyTaskFilters,
  hasTaskFilters,
  overdueDays,
  readTaskFilters,
  taskDate,
  taskFilterQuery,
  taskInput,
  taskPriorities,
  taskStatuses,
  writeTaskFilters,
  type TaskFilters,
} from "./task-utils";
import styles from "./tasks.module.css";
import { moveTaskToPosition } from "./task-moves";

type Column = PaginatedTasks & { page: number };
type Move = { task: Task; status: TaskStatus; first: boolean };

export default function TasksPage() {
  const { project } = useProjectContext();
  const workspace = useWorkspace();
  const { accessToken } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const paramsString = params.toString();
  const filters = useMemo(
    () => readTaskFilters(new URLSearchParams(paramsString)),
    [paramsString],
  );
  const view = params.get("view") === "list" ? "list" : "board";
  const page = Math.max(1, Number.parseInt(params.get("page") || "1", 10) || 1);
  const taskId = params.get("task");
  const canDelete = projectPermissions(workspace.role, project.role).canManage;
  const queryKey = JSON.stringify(taskFilterQuery(filters));
  const [searchState, setSearchState] = useState({
    source: filters.search,
    value: filters.search,
  });
  if (searchState.source !== filters.search)
    setSearchState({ source: filters.search, value: filters.search });
  const search =
    searchState.source === filters.search ? searchState.value : filters.search;
  const collectionKey = `${project.id}|${queryKey}|${view}`;
  const currentCollection = useRef(collectionKey);
  useEffect(() => {
    currentCollection.current = collectionKey;
  }, [collectionKey]);
  const [list, setList] = useState<PaginatedTasks | null>(null);
  const [columns, setColumns] = useState<Partial<Record<TaskStatus, Column>>>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [membersError, setMembersError] = useState("");
  const [memberReload, setMemberReload] = useState(0);
  const [filtering, setFiltering] = useState(false);
  const [creating, setCreating] = useState<TaskStatus | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Task | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [actionError, setActionError] = useState("");
  const [mutationBusy, setMutationBusy] = useState(false);
  const [moving, setMoving] = useState<Move | null>(null);
  const [dragged, setDragged] = useState<Task | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [loadingColumn, setLoadingColumn] = useState<TaskStatus | null>(null);
  const [columnErrors, setColumnErrors] = useState<
    Partial<Record<TaskStatus, string>>
  >({});
  const [activeStatus, setActiveStatus] = useState<TaskStatus>("todo");
  const [missingId, setMissingId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const statuses = filters.statuses.length
    ? filters.statuses
    : taskStatuses.map((status) => status.value);
  const mobileStatus = statuses.includes(activeStatus)
    ? activeStatus
    : statuses[0];
  function navigate(next: URLSearchParams, push = false) {
    const url = `${pathname}${next.size ? `?${next}` : ""}`;
    if (push) router.push(url, { scroll: false });
    else router.replace(url, { scroll: false });
  }
  function applyFilters(next: TaskFilters, mode = view) {
    setNotice("");
    const query = writeTaskFilters(next, new URLSearchParams(paramsString));
    query.set("view", mode);
    navigate(query);
  }
  function openTask(id: string | null) {
    setNotice("");
    const query = new URLSearchParams(paramsString);
    if (id) query.set("task", id);
    else query.delete("task");
    navigate(query, Boolean(id));
  }
  function changePage(next: number) {
    const query = new URLSearchParams(paramsString);
    query.set("page", String(next));
    navigate(query);
  }
  useEffect(() => {
    if (search === filters.search) return;
    const timer = setTimeout(() => {
      const current = readTaskFilters(new URLSearchParams(paramsString));
      const query = writeTaskFilters(
        { ...current, search },
        new URLSearchParams(paramsString),
      );
      router.replace(`${pathname}?${query}`, { scroll: false });
    }, 350);
    return () => clearTimeout(timer);
  }, [search, filters.search, paramsString, router, pathname]);
  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      setColumnErrors({});
      const query = JSON.parse(queryKey) as TaskQuery;
      try {
        if (view === "list") {
          const data = await getTasks(
            accessToken!,
            workspace.slug,
            project.id,
            { ...query, page, page_size: 20 },
          );
          if (!cancelled) setList(data);
        } else {
          const requested = query.status?.length
            ? query.status
            : taskStatuses.map((status) => status.value);
          const results = await Promise.all(
            requested.map(
              async (status) =>
                [
                  status,
                  {
                    ...(await getTasks(
                      accessToken!,
                      workspace.slug,
                      project.id,
                      {
                        ...query,
                        status: [status],
                        ordering: "position",
                        page: 1,
                        page_size: 4,
                      },
                    )),
                    page: 1,
                  },
                ] as const,
            ),
          );
          if (!cancelled) setColumns(Object.fromEntries(results));
        }
      } catch (err) {
        if (!cancelled) {
          if (
            view === "list" &&
            page > 1 &&
            err instanceof ApiError &&
            err.status === 404 &&
            /invalid page/i.test(err.message)
          ) {
            const query = new URLSearchParams(window.location.search);
            query.set("page", String(page - 1));
            router.replace(`${pathname}?${query}`, { scroll: false });
          } else
            setError(
              err instanceof Error ? err.message : "Unable to load tasks.",
            );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [
    accessToken,
    workspace.slug,
    project.id,
    queryKey,
    view,
    page,
    reload,
    router,
    pathname,
  ]);
  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    async function loadMembers() {
      setMembersLoading(true);
      setMembersError("");
      try {
        const all: ProjectMember[] = [];
        for (let page = 1; ; page++) {
          const data = await getProjectMembers(
            accessToken!,
            workspace.slug,
            project.id,
            page,
          );
          if (cancelled) return;
          all.push(...data.results);
          if (!data.next) break;
        }
        setMembers(all);
      } catch (err) {
        if (!cancelled)
          setMembersError(
            err instanceof Error
              ? err.message
              : "Unable to load project members.",
          );
      } finally {
        if (!cancelled) setMembersLoading(false);
      }
    }
    void loadMembers();
    return () => {
      cancelled = true;
    };
  }, [accessToken, workspace.slug, project.id, memberReload]);
  const memberProps = {
    members,
    membersLoading,
    membersError,
    onRetryMembers: () => setMemberReload((value) => value + 1),
  };
  async function showMore(status: TaskStatus) {
    const current = columns[status];
    if (!accessToken || !current?.next || loadingColumn) return;
    const requestCollection = collectionKey;
    setLoadingColumn(status);
    setColumnErrors((previous) => ({ ...previous, [status]: "" }));
    try {
      const data = await getTasks(accessToken, workspace.slug, project.id, {
        ...taskFilterQuery(filters),
        status: [status],
        ordering: "position",
        page: current.page + 1,
        page_size: 4,
      });
      if (currentCollection.current !== requestCollection) return;
      setColumns((previous) => ({
        ...previous,
        [status]: {
          ...data,
          page: current.page + 1,
          results: [
            ...new Map(
              [...current.results, ...data.results].map((task) => [
                task.id,
                task,
              ]),
            ).values(),
          ],
        },
      }));
    } catch (err) {
      if (currentCollection.current === requestCollection) {
        setColumnErrors((previous) => ({
          ...previous,
          [status]: err instanceof Error ? err.message : "Unable to load more tasks.",
        }));
      }
    } finally {
      setLoadingColumn(null);
    }
  }
  function requestDelete(task: Task) {
    setDeleting(task);
    setActionError("");
    setBlocked(false);
  }
  function closeAction() {
    setDeleting(null);
    setMoving(null);
    setActionError("");
    setBlocked(false);
  }
  async function confirmDelete() {
    if (!accessToken || !deleting || mutationBusy) return;
    setMutationBusy(true);
    setActionError("");
    try {
      await deleteTask(accessToken, workspace.slug, project.id, deleting.id);
      setDeleting(null);
      if (taskId === deleting.id) openTask(null);
      setReload((value) => value + 1);
      setNotice("Task deleted.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setDeleting(null);
        if (taskId) setMissingId(taskId);
        setReload((value) => value + 1);
      } else {
        setActionError(
          err instanceof Error ? err.message : "Unable to delete task.",
        );
        setBlocked(err instanceof ApiError && err.status === 403);
      }
    } finally {
      setMutationBusy(false);
    }
  }
  async function performMove(
    task: Task,
    status: TaskStatus,
    before: Task | null = null,
    first = false,
  ) {
    if (!accessToken || mutationBusy) return;
    setMutationBusy(true);
    setActionError("");
    setError("");
    setNotice("");
    try {
      await moveTaskToPosition(
        accessToken,
        workspace.slug,
        project.id,
        task.id,
        status,
        before?.id ?? null,
        first,
      );
      setMoving(null);
      setNotice(
        `Moved ${task.title} to ${taskStatuses.find((item) => item.value === status)?.label}.`,
      );
    } catch (err) {
      const fields = err instanceof ApiError ? err.errors : null;
      const message = fields ? Object.values(fields).flat().join(" ") : "";
      const text =
        message ||
        (err instanceof Error ? err.message : "Unable to move task.");
      setActionError(text);
    } finally {
      setMutationBusy(false);
      setDragged(null);
      setDropTarget(null);
      setReload((value) => value + 1);
    }
  }
  function drop(
    event: DragEvent,
    status: TaskStatus,
    before: Task | null = null,
  ) {
    event.preventDefault();
    event.stopPropagation();
    if (dragged && !mutationBusy && before?.id !== dragged.id)
      void performMove(dragged, status, before);
    setDragged(null);
    setDropTarget(null);
  }
  const priority = (task: Task) => (
    <span className={`${styles.priority} ${styles[task.priority]}`}>
      <span className={styles.dot} />
      {task.priority.charAt(0).toUpperCase() + task.priority.slice(1)}
    </span>
  );
  const badge = (task: Task) => (
    <span className={`${styles.badge} ${styles[task.status]}`}>
      {taskStatuses.find((status) => status.value === task.status)?.label}
    </span>
  );
  const due = (task: Task, year = false) =>
    task.due_date ? (
      <span
        className={`${styles.due} ${overdueDays(task.due_date, task.status) ? styles.overdue : ""}`}
      >
        <TaskIcon name="calendar" />
        <time dateTime={task.due_date}>{taskDate(task.due_date, year)}</time>
      </span>
    ) : (
      <span className={styles.hint}>{year ? "No due date" : ""}</span>
    );
  const assignee = (task: Task, email = false) => (
    <span
      className={styles.assignee}
      title={task.assignee_email || "Unassigned"}
    >
      {task.assignee !== null ? (
        <>
          <Avatar
            src={task.assignee_avatar}
            fallback={(task.assignee_email || "U").charAt(0).toUpperCase()}
            size={24}
            className={styles.avatar}
          />
          {email && <span>{task.assignee_email}</span>}
        </>
      ) : email ? (
        <span className={styles.hint}>Unassigned</span>
      ) : null}
    </span>
  );
  const actions = (task: Task) => (
    <TaskActions
      task={task}
      canDelete={canDelete}
      disabled={mutationBusy || loading}
      onOpen={() => openTask(task.id)}
      onMove={() => {
        setMoving({ task, status: task.status, first: false });
        setActionError("");
      }}
      onDelete={() => requestDelete(task)}
    />
  );
  const total =
    view === "list"
      ? list?.count || 0
      : Object.values(columns).reduce(
          (sum, column) => sum + (column?.count || 0),
          0,
        );
  const filtered = hasTaskFilters(filters);
  const chips: { label: string; clear: () => void }[] = [
    ...filters.statuses.map((status) => ({
      label: `Status: ${taskStatuses.find((item) => item.value === status)?.label}`,
      clear: () =>
        applyFilters({
          ...filters,
          statuses: filters.statuses.filter((value) => value !== status),
        }),
    })),
    ...(filters.assignee
      ? [
          {
            label: `Assignee: ${filters.assignee === "me" ? "Me" : filters.assignee === "unassigned" ? "Unassigned" : members.find((member) => String(member.user_id) === filters.assignee)?.user_email || "Member"}`,
            clear: () => applyFilters({ ...filters, assignee: "" }),
          },
        ]
      : []),
    ...(filters.priority
      ? [
          {
            label: `Priority: ${filters.priority.charAt(0).toUpperCase() + filters.priority.slice(1)}`,
            clear: () => applyFilters({ ...filters, priority: "" }),
          },
        ]
      : []),
    ...(filters.overdue
      ? [
          {
            label: "Overdue",
            clear: () => applyFilters({ ...filters, overdue: false }),
          },
        ]
      : []),
    ...(filters.dueBefore
      ? [
          {
            label: `Due before ${taskDate(filters.dueBefore)}`,
            clear: () => applyFilters({ ...filters, dueBefore: "" }),
          },
        ]
      : []),
  ];
  const empty = (missing = false) => (
    <section className={styles.empty}>
      <span className={styles.emptyIcon}>
        <TaskIcon name={filtered || missing ? "search" : "tasks"} />
      </span>
      <h2>
        {missing
          ? "This task no longer exists"
          : filtered
            ? "No tasks match your filters"
            : "No tasks yet"}
      </h2>
      <p className={styles.muted}>
        {missing
          ? "It may have been deleted by someone else, or you may no longer have access."
          : filtered
            ? "Try removing a filter or searching for something else."
            : `Create the first task for ${project.name} and assign it to a teammate.`}
      </p>
      <button
        className={
          filtered || missing ? styles.secondaryButton : styles.primaryButton
        }
        onClick={() =>
          missing
            ? openTask(null)
            : filtered
              ? applyFilters(emptyTaskFilters)
              : setCreating("todo")
        }
      >
        {missing ? "Back to tasks" : filtered ? "Clear filters" : "New task"}
      </button>
    </section>
  );
  if (taskId && missingId === taskId) return empty(true);
  return (
    <div className={styles.root}>
      {notice && (
        <p className={styles.notice} role="status" aria-live="polite">
          {notice}
        </p>
      )}
      {(loading || error || total > 0 || filtered) && (
        <div className={styles.toolbar}>
          <div className={styles.toolbarFilters}>
            <label className={styles.search}>
              <span className={styles.srOnly}>Search tasks</span>
              <TaskIcon name="search" />
              <input
                placeholder="Search tasks…"
                value={search}
                maxLength={200}
                onChange={(event) =>
                  setSearchState({
                    source: filters.search,
                    value: event.target.value,
                  })
                }
              />
            </label>
            <div className={styles.desktopFilters}>
              <AssigneePicker
                filter
                members={members}
                value={filters.assignee}
                onChange={(assignee) => applyFilters({ ...filters, assignee })}
                loading={membersLoading}
                error={membersError}
                onRetry={memberProps.onRetryMembers}
              />
            </div>
            <select
              aria-label="Filter by priority"
              className={`${styles.filterSelect} ${styles.desktopFilters} ${filters.priority ? styles.activeFilter : ""}`}
              value={filters.priority}
              onChange={(event) =>
                applyFilters({
                  ...filters,
                  priority: event.target.value as TaskFilters["priority"],
                })
              }
            >
              <option value="">Priority</option>
              {taskPriorities.map((value) => (
                <option key={value} value={value}>
                  {value.charAt(0).toUpperCase() + value.slice(1)}
                </option>
              ))}
            </select>
            <button
              type="button"
              className={`${styles.iconButton} ${styles.desktopFilters}`}
              aria-label="All task filters"
              onClick={() => setFiltering(true)}
            >
              <TaskIcon name="filter" />
            </button>
          </div>
          <button
            className={`${styles.iconButton} ${styles.mobileFilter}`}
            aria-label="Task filters and view"
            onClick={() => setFiltering(true)}
          >
            <TaskIcon name="filter" />
          </button>
          <div className={styles.viewActions}>
            <div className={styles.toggle} aria-label="Task view">
              {(["board", "list"] as const).map((mode) => (
                <button
                  key={mode}
                  className={view === mode ? styles.activeView : ""}
                  aria-pressed={view === mode}
                  onClick={() => applyFilters(filters, mode)}
                >
                  <TaskIcon name={mode} />
                  {mode === "board" ? "Board" : "List"}
                </button>
              ))}
            </div>
            <button
              className={styles.primaryButton}
              onClick={() => setCreating("todo")}
            >
              New task
            </button>
          </div>
        </div>
      )}
      {(filtered || (view === "list" && total > 0)) && (
        <div className={styles.chips}>
          {chips.map((chip) => (
            <button
              key={chip.label}
              className={styles.chip}
              onClick={chip.clear}
              aria-label={`Remove ${chip.label}`}
            >
              {chip.label}
              <span aria-hidden="true">×</span>
            </button>
          ))}
          {view === "list" && (
            <button
              className={`${styles.chip} ${styles.mobileSort}`}
              onClick={() => setFiltering(true)}
            >
              Sort: {orderingLabels[filters.ordering]}
            </button>
          )}
          {filtered && (
            <button
              className={styles.clearButton}
              onClick={() => applyFilters(emptyTaskFilters)}
            >
              Clear all
            </button>
          )}
        </div>
      )}
      {error && (
        <div className={styles.alert} role="alert">
          {error}{" "}
          <button
            className={styles.clearButton}
            onClick={() => setReload((value) => value + 1)}
          >
            Try again
          </button>
        </div>
      )}
      {actionError && !moving && !deleting && (
        <div className={styles.alert} role="alert">
          {actionError}{" "}
          <button
            className={styles.clearButton}
            onClick={() => setActionError("")}
          >
            Dismiss
          </button>
        </div>
      )}
      {loading ? (
        <div className={styles.status} role="status">
          Loading tasks…
        </div>
      ) : error ? null : !total ? (
        empty()
      ) : view === "board" ? (
        <>
          <div
            className={styles.mobileStatusTabs}
            aria-label="Task status columns"
          >
            {statuses.map((status) => (
              <button
                key={status}
                className={
                  mobileStatus === status ? styles.selectedPill : styles.pill
                }
                aria-pressed={mobileStatus === status}
                onClick={() => setActiveStatus(status)}
              >
                {taskStatuses.find((item) => item.value === status)?.label} ·{" "}
                {columns[status]?.count || 0}
              </button>
            ))}
          </div>
          <div className={styles.board} aria-busy={mutationBusy}>
            {statuses.map((status) => (
              <section
                key={status}
                className={`${styles.column} ${mobileStatus !== status ? styles.hiddenColumn : ""} ${dropTarget === status ? styles.dropColumn : ""}`}
                aria-label={`${taskStatuses.find((item) => item.value === status)?.label} column`}
                onDragOver={(event) => {
                  if (dragged && !mutationBusy) {
                    event.preventDefault();
                    setDropTarget(status);
                  }
                }}
                onDrop={(event) => drop(event, status)}
              >
                <header className={styles.columnHeader}>
                  <span className={`${styles.dot} ${styles[status]}`} />
                  <span>
                    {taskStatuses.find((item) => item.value === status)?.label}
                  </span>
                  <small>{columns[status]?.count || 0}</small>
                  <button
                    aria-label={`New task in ${taskStatuses.find((item) => item.value === status)?.label}`}
                    onClick={() => setCreating(status)}
                  >
                    +
                  </button>
                </header>
                {columns[status]?.results.map((task) => (
                  <article
                    key={task.id}
                    data-task-id={task.id}
                    className={`${styles.taskCard} ${dragged?.id === task.id ? styles.dragging : ""} ${dropTarget === task.id ? styles.dropBefore : ""}`}
                    draggable={!mutationBusy}
                    onDragStart={(event) => {
                      setDragged(task);
                      event.dataTransfer.effectAllowed = "move";
                      event.dataTransfer.setData("text/plain", task.id);
                    }}
                    onDragEnd={() => {
                      setDragged(null);
                      setDropTarget(null);
                    }}
                    onDragOver={(event) => {
                      if (dragged && !mutationBusy) {
                        event.preventDefault();
                        event.stopPropagation();
                        setDropTarget(task.id);
                      }
                    }}
                    onDrop={(event) => drop(event, status, task)}
                  >
                    <div className={styles.cardTitle}>
                      <button
                        className={styles.titleButton}
                        onClick={() => openTask(task.id)}
                      >
                        {task.title}
                      </button>
                      {actions(task)}
                    </div>
                    {priority(task)}
                    <div className={styles.cardFooter}>
                      {due(task)}
                      {assignee(task)}
                    </div>
                  </article>
                ))}
                {!columns[status]?.count && (
                  <p className={styles.columnEmpty}>No tasks in this column.</p>
                )}
                {columnErrors[status] && (
                  <p className={styles.alert} role="alert">
                    {columnErrors[status]}
                  </p>
                )}
                {columns[status]?.next && (
                  <button
                    className={styles.showMore}
                    aria-label={
                      columnErrors[status]
                        ? `Retry loading more ${taskStatuses.find((item) => item.value === status)?.label} tasks`
                        : undefined
                    }
                    disabled={Boolean(loadingColumn) || mutationBusy}
                    onClick={() => void showMore(status)}
                  >
                    {loadingColumn === status
                      ? "Loading…"
                      : columnErrors[status]
                        ? "Retry"
                        : `Show ${(columns[status]?.count || 0) - (columns[status]?.results.length || 0)} more`}
                  </button>
                )}
              </section>
            ))}
          </div>
        </>
      ) : (
        list && (
          <div className={styles.tableCard}>
            <div className={styles.desktopTable}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    {[
                      { name: "TASK", ordering: "title" },
                      { name: "STATUS", ordering: "status" },
                      { name: "PRIORITY", ordering: "priority" },
                      { name: "ASSIGNEE", ordering: null },
                      { name: "DUE", ordering: "due_date" },
                    ].map((column) => (
                      <th
                        key={column.name}
                        aria-sort={
                          column.ordering &&
                          filters.ordering.replace("-", "") === column.ordering
                            ? filters.ordering.startsWith("-")
                              ? "descending"
                              : "ascending"
                            : undefined
                        }
                      >
                        {column.ordering ? (
                          <button
                            className={styles.sortButton}
                            onClick={() =>
                              applyFilters({
                                ...filters,
                                ordering: (filters.ordering === column.ordering
                                  ? `-${column.ordering}`
                                  : column.ordering) as TaskFilters["ordering"],
                              })
                            }
                          >
                            {column.name}
                            {filters.ordering.replace("-", "") ===
                              column.ordering && (
                              <span>
                                {filters.ordering.startsWith("-") ? "↓" : "↑"}
                              </span>
                            )}
                          </button>
                        ) : (
                          column.name
                        )}
                      </th>
                    ))}
                    <th aria-label="Task actions" />
                  </tr>
                </thead>
                <tbody>
                  {list.results.map((task) => (
                    <tr key={task.id}>
                      <td>
                        <button
                          className={styles.titleButton}
                          onClick={() => openTask(task.id)}
                        >
                          {task.title}
                        </button>
                      </td>
                      <td>{badge(task)}</td>
                      <td>{priority(task)}</td>
                      <td>{assignee(task, true)}</td>
                      <td>{due(task, true)}</td>
                      <td>{actions(task)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={styles.mobileList}>
              {list.results.map((task) => (
                <article className={styles.taskCard} key={task.id}>
                  <div className={styles.cardTitle}>
                    <button
                      className={styles.titleButton}
                      onClick={() => openTask(task.id)}
                    >
                      {task.title}
                    </button>
                    {actions(task)}
                  </div>
                  <div className={styles.mobileTaskMeta}>
                    {badge(task)}
                    {priority(task)}
                  </div>
                  <div className={styles.mobileTaskFooter}>
                    {due(task)}
                    {assignee(task, true)}
                  </div>
                </article>
              ))}
            </div>
            <div className={styles.pagination}>
              <span>
                Showing {list.results.length ? (page - 1) * 20 + 1 : 0}–
                {list.results.length
                  ? (page - 1) * 20 + list.results.length
                  : 0}{" "}
                of {list.count}
              </span>
              <div className={styles.actions}>
                <button
                  className={styles.secondaryButton}
                  disabled={!list.previous}
                  onClick={() => changePage(page - 1)}
                >
                  Previous
                </button>
                <button
                  className={styles.secondaryButton}
                  disabled={!list.next}
                  onClick={() => changePage(page + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )
      )}
      {(total > 0 || filtered) && (
        <button
          className={styles.mobileNew}
          aria-label="New task"
          onClick={() => setCreating(view === "board" ? mobileStatus : "todo")}
        >
          +
        </button>
      )}
      {filtering && (
        <TaskFiltersDialog
          filters={filters}
          view={view}
          {...memberProps}
          onClose={() => setFiltering(false)}
          onApply={(next, mode) => {
            setFiltering(false);
            applyFilters(next, mode);
          }}
        />
      )}
      {creating && accessToken && (
        <TaskDialog
          title="New task"
          description={`Add a task to ${project.name}.`}
          onClose={() => setCreating(null)}
          busy={saving}
        >
          <TaskForm
            initial={taskInput(undefined, creating)}
            {...memberProps}
            onBusyChange={setSaving}
            onCancel={() => setCreating(null)}
            onSubmit={async (input) => {
              await createTask(accessToken, workspace.slug, project.id, input);
              setCreating(null);
              setReload((value) => value + 1);
              setNotice("Task created.");
            }}
          />
        </TaskDialog>
      )}
      {taskId && accessToken && !deleting && (
        <TaskDrawer
          key={taskId}
          token={accessToken}
          slug={workspace.slug}
          projectId={project.id}
          taskId={taskId}
          canDelete={canDelete}
          {...memberProps}
          onClose={() => openTask(null)}
          onSaved={() => {
            setReload((value) => value + 1);
            setNotice("Task saved.");
          }}
          onDelete={requestDelete}
          onMissing={() => setMissingId(taskId)}
        />
      )}
      {deleting && (
        <TaskDialog
          title={blocked ? "Can’t delete this task" : "Delete this task?"}
          description={
            blocked
              ? deleting.title
              : `“${deleting.title}” will be permanently deleted. This can’t be undone.`
          }
          onClose={closeAction}
          busy={mutationBusy}
        >
          {actionError && (
            <p className={styles.alert} role="alert">
              {actionError}
            </p>
          )}
          <div className={styles.actions}>
            <button
              className={styles.secondaryButton}
              disabled={mutationBusy}
              onClick={closeAction}
            >
              {blocked ? "Close" : "Cancel"}
            </button>
            {!blocked && (
              <button
                className={styles.dangerButton}
                disabled={mutationBusy}
                onClick={() => void confirmDelete()}
              >
                {mutationBusy ? "Deleting…" : "Delete task"}
              </button>
            )}
          </div>
        </TaskDialog>
      )}
      {moving && (
        <TaskDialog
          title="Move task"
          description={`“${moving.task.title}”`}
          onClose={closeAction}
          busy={mutationBusy}
        >
          <form
            className={styles.form}
            onSubmit={(event) => {
              event.preventDefault();
              void performMove(moving.task, moving.status, null, moving.first);
            }}
          >
            <fieldset className={styles.filterGroup}>
              <legend>Status</legend>
              {taskStatuses.map((status) => (
                <label className={styles.radioOption} key={status.value}>
                  <input
                    type="radio"
                    name="move-task-status"
                    value={status.value}
                    checked={moving.status === status.value}
                    disabled={mutationBusy}
                    onChange={() =>
                      setMoving(
                        (current) =>
                          current && { ...current, status: status.value },
                      )
                    }
                  />
                  <span>
                    <strong>{status.label}</strong>
                    <small className={styles.hint}>{status.description}</small>
                  </span>
                </label>
              ))}
            </fieldset>
            <div className={styles.field}>
              <label htmlFor="move-task-position">Position</label>
              <select
                id="move-task-position"
                value={moving.first ? "first" : "last"}
                disabled={mutationBusy}
                onChange={(event) =>
                  setMoving(
                    (current) =>
                      current && {
                        ...current,
                        first: event.target.value === "first",
                      },
                  )
                }
              >
                <option value="last">At the end of the column</option>
                <option value="first">At the beginning of the column</option>
              </select>
            </div>
            {actionError && (
              <p className={styles.alert} role="alert">
                {actionError}
              </p>
            )}
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.secondaryButton}
                disabled={mutationBusy}
                onClick={closeAction}
              >
                Cancel
              </button>
              <button className={styles.primaryButton} disabled={mutationBusy}>
                {mutationBusy ? "Moving…" : "Move task"}
              </button>
            </div>
          </form>
        </TaskDialog>
      )}
    </div>
  );
}
