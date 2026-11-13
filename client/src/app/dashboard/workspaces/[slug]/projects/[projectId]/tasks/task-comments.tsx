import Image from "next/image";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import Avatar from "@/components/ui/Avatar";
import {
  ApiError,
  createTaskComment,
  deleteTaskComment,
  downloadCommentAttachment,
  getTaskComments,
  updateTaskComment,
  type CurrentUser,
  type ProjectMember,
  type TaskComment,
} from "@/lib/api";
import CommentInput from "./comment-input";
import CommentActions from "./comment-actions";
import styles from "./task-comments.module.css";
import taskStyles from "./tasks.module.css";

const commentLimit = 5000;
const timestamp = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((word) => word.charAt(0).toUpperCase()).join("");
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 429) return "You’re commenting too fast. Please wait a moment and try again.";
    const body = error.errors?.body ?? error.errors?.attachment ?? error.errors?.reply_to;
    if (body) return Array.isArray(body) ? body.join(" ") : body;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export default function TaskComments({
  token, slug, projectId, taskId, user, members, canModerate, active, onCountChange, onBusyChange,
}: {
  token: string;
  slug: string;
  projectId: string;
  taskId: string;
  user: CurrentUser;
  members: ProjectMember[];
  canModerate: boolean;
  active: boolean;
  onCountChange: (count: number) => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const [comments, setComments] = useState<TaskComment[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [pageError, setPageError] = useState("");
  const [reload, setReload] = useState(0);
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<TaskComment | null>(null);
  const [attachment, setAttachment] = useState<File>();
  const [downloadError, setDownloadError] = useState("");
  const composerId = useId();
  const [postError, setPostError] = useState("");
  const [editing, setEditing] = useState<{ id: string; body: string } | null>(null);
  const [editError, setEditError] = useState("");
  const [deleting, setDeleting] = useState<TaskComment | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [pending, setPending] = useState<"post" | "edit" | "delete" | null>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const entries = useRef<HTMLDivElement>(null);
  const postedId = useRef<string | null>(null);
  const dialogTitle = useId();
  const dialogDescription = useId();
  const draftLength = Array.from(draft).length;
  const editLength = editing ? Array.from(editing.body).length : 0;
  const busy = Boolean(pending) || loading || loadingMore;
  const canPost = !busy && !loadError && Boolean(draft.trim() || attachment) && draftLength <= commentLimit;
  const commentsById = new Map(comments.map((comment) => [comment.id, comment]));
  const scope = [token, slug, projectId, taskId] as const;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setLoadError("");
      setPageError("");
      try {
        const result = await getTaskComments(token, slug, projectId, taskId);
        if (cancelled) return;
        setComments(result.results);
        setCount(result.count);
        onCountChange(result.count);
        setPage(1);
        setHasMore(Boolean(result.next));
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [token, slug, projectId, taskId, reload, onCountChange]);

  useEffect(() => {
    if (deleting) deleteDialog.current?.showModal();
  }, [deleting]);

  useEffect(() => {
    if (!postedId.current) return;
    const posted = document.getElementById(`comment-${postedId.current}`);
    if (entries.current?.contains(posted)) {
      posted?.scrollIntoView({ block: "nearest" });
    }
    postedId.current = null;
  }, [comments]);

  function closeDeleteDialog() {
    deleteDialog.current?.close();
    setDeleting(null);
  }

  async function loadMore() {
    if (busy || !hasMore) return;
    setLoadingMore(true);
    setPageError("");
    try {
      const result = await getTaskComments(...scope, page + 1);
      setComments((previous) => {
        const ids = new Set(result.results.map((comment) => comment.id));
        // A just-posted comment may already be visible beyond the loaded pages.
        return [...previous.filter((comment) => !ids.has(comment.id)), ...result.results]
          .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
      });
      setCount(result.count);
      onCountChange(result.count);
      setHasMore(Boolean(result.next));
      setPage(page + 1);
    } catch (error) {
      setPageError(errorMessage(error));
    } finally {
      setLoadingMore(false);
    }
  }

  async function post(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canPost) return;
    setPending("post");
    onBusyChange(true);
    setPostError("");
    try {
      const comment = await createTaskComment(...scope, draft.trim(), replyTo?.id, attachment);
      postedId.current = comment.id;
      setComments((previous) => [...previous, comment]);
      setCount(count + 1);
      onCountChange(count + 1);
      setDraft("");
      setReplyTo(null);
      setAttachment(undefined);
    } catch (error) {
      setPostError(errorMessage(error));
    } finally {
      setPending(null);
      onBusyChange(false);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !editing || editLength > commentLimit) return;
    setPending("edit");
    onBusyChange(true);
    setEditError("");
    try {
      const updated = await updateTaskComment(...scope, editing.id, editing.body.trim());
      setComments((previous) => previous.map((comment) => comment.id === updated.id ? updated : comment));
      setEditing(null);
    } catch (error) {
      setEditError(errorMessage(error));
    } finally {
      setPending(null);
      onBusyChange(false);
    }
  }

  async function download(comment: TaskComment) {
    if (!comment.attachment) return;
    setDownloadError("");
    try {
      const file = await downloadCommentAttachment(...scope, comment.id);
      const url = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = url;
      link.download = comment.attachment.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setDownloadError(errorMessage(error));
    }
  }

  async function remove() {
    if (busy || !deleting) return;
    setPending("delete");
    onBusyChange(true);
    setDeleteError("");
    try {
      await deleteTaskComment(...scope, deleting.id);
      setComments((previous) => previous.filter((comment) => comment.id !== deleting.id));
      setCount(count - 1);
      onCountChange(count - 1);
      closeDeleteDialog();
      // A deletion shifts the page boundaries, so refresh before loading more.
      if (hasMore) setReload((value) => value + 1);
    } catch (error) {
      setDeleteError(errorMessage(error));
    } finally {
      setPending(null);
      onBusyChange(false);
    }
  }

  return (
    <div className={styles.thread} data-comment-thread hidden={!active}>
      <div className={styles.entries} ref={entries} aria-busy={loading || loadingMore}>
        {downloadError && <p role="alert" className={taskStyles.alert}>{downloadError}</p>}
        {loading && <p role="status" className={taskStyles.muted}>Loading comments…</p>}
        {loadError && (
          <>
            <p className={taskStyles.alert} role="alert">{loadError}</p>
            <button type="button" className={taskStyles.secondaryButton} onClick={() => setReload((value) => value + 1)}>
              Try again
            </button>
          </>
        )}
        {!loading && !loadError && !comments.length && (
          <div className={styles.empty}>
            <span><Image src="/icons/comments/empty.svg" alt="" width={20} height={20} /></span>
            <h3>No comments yet</h3>
            <p>Start the conversation about this task.</p>
          </div>
        )}
        {comments.map((comment) => {
          const own = comment.author_id === user.id;
          const avatar = own ? user.avatar : members.find((member) => member.user_id === comment.author_id)?.avatar;
          // Django assigns both timestamps separately on insert.
          const edited = Boolean(comment.edited_at) ||
            Date.parse(comment.updated_at) - Date.parse(comment.created_at) >= 1000;
          return (
            <article className={comment.reply_to ? styles.reply : styles.comment} id={`comment-${comment.id}`} key={comment.id}>
              <Avatar
                className={`${styles.avatar} ${comment.author_id === null ? styles.deletedAvatar : ""}`}
                src={avatar}
                fallback={comment.author_id === null ? "?" : initials(comment.author_name)}
                size={32}
              />
              <div className={styles.commentContent}>
                <div className={styles.byline}>
                  <strong>{comment.author_name}</strong>
                  {own && <span className={styles.you}>You</span>}
                  <span className={styles.date}>
                    <time dateTime={comment.created_at}>{timestamp.format(new Date(comment.created_at))}</time>
                    {edited && " · edited"}
                  </span>
                </div>
                {editing?.id === comment.id ? (
                  <form className={styles.editor} onSubmit={save}>
                    <CommentInput
                      members={members}
                      aria-label="Edit comment"
                      aria-invalid={editLength > commentLimit || Boolean(editError)}
                      autoFocus
                      disabled={pending === "edit"}
                      value={editing.body}
                      onValueChange={(body) => {
                        setEditing({ id: comment.id, body });
                        setEditError("");
                      }}
                    />
                    {(editLength > commentLimit || editError) && (
                      <p className={styles.fieldError} role="alert">
                        {editLength > commentLimit ? "Comment cannot exceed 5000 characters." : editError}
                      </p>
                    )}
                    <div className={styles.editorFooter}>
                      <span className={taskStyles.counter}>{editLength} / {commentLimit}</span>
                      <button type="button" className={taskStyles.secondaryButton} disabled={Boolean(pending)} onClick={() => setEditing(null)}>Cancel</button>
                      <button className={taskStyles.primaryButton} disabled={busy || (!editing.body.trim() && !comment.attachment) || editLength > commentLimit || editing.body.trim() === comment.body}>
                        {pending === "edit" ? "Saving…" : "Save"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    {comment.reply_to && (
                      commentsById.has(comment.reply_to) ? (
                        <button type="button" className={styles.replyContext} onClick={() => {
                          const parent = document.getElementById("comment-" + comment.reply_to);
                          if (!parent) return;
                          parent.scrollIntoView({ block: "center" });
                          parent.animate(
                            [{ backgroundColor: "#e0e7ff" }, { backgroundColor: "transparent" }],
                            { duration: 1000 },
                          );
                        }}>
                          Reply to {commentsById.get(comment.reply_to)?.author_name}
                        </button>
                      ) : <p className={styles.replyContext}>Reply to an earlier comment</p>
                    )}
                    {comment.body && (
                      <p className={styles.body}>{comment.body.split(/(@[\w.+-]+@[\w-]+(?:\.[\w-]+)+)/).map((part, index) =>
                        comment.mentions.some((email) => "@" + email.toLowerCase() === part.toLowerCase())
                          ? <span className={styles.mention} key={index}>{part}</span>
                          : part,
                      )}</p>
                    )}
                    {comment.attachment && (
                      <button className={styles.attachment} type="button" onClick={() => void download(comment)}>
                        Download {comment.attachment.filename}
                      </button>
                    )}
                    <button
                      className={styles.replyButton}
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setReplyTo(comment);
                        setPostError("");
                        document.getElementById(composerId)?.focus();
                      }}
                    >
                      Reply
                    </button>
                  </>
                )}
              </div>
              {(own || canModerate) && editing?.id !== comment.id && (
                <CommentActions
                  author={comment.author_name}
                  disabled={busy || Boolean(editing)}
                  onEdit={own ? () => { setEditError(""); setEditing({ id: comment.id, body: comment.body }); } : undefined}
                  onDelete={() => { setDeleteError(""); setDeleting(comment); }}
                />
              )}
            </article>
          );
        })}
        {pageError && <p className={taskStyles.alert} role="alert">{pageError}</p>}
        {hasMore && !loadError && (
          <button type="button" className={styles.loadMore} onClick={loadMore} disabled={busy}>
            {loadingMore
              ? "Loading…"
              : pageError
                ? "Retry loading comments"
                : count > comments.length
                  ? `Load ${count - comments.length} more ${count - comments.length === 1 ? "comment" : "comments"}`
                  : "Load more comments"}
          </button>
        )}
        {!canModerate && comments.length > 0 && (
          <p className={styles.permissionHint}>You can edit or delete your own comments.</p>
        )}
      </div>
      <div className={styles.composerArea}>
        {postError && <p className={taskStyles.alert} role="alert">{postError}</p>}
        {replyTo && (
          <div className={styles.replyDraft}>
            <span>Replying to {replyTo.author_name}</span>
            <button type="button" onClick={() => setReplyTo(null)} disabled={pending === "post"} aria-label="Cancel reply">×</button>
          </div>
        )}
        <form className={styles.composer} onSubmit={post}>
          <Avatar className={`${styles.avatar} ${styles.composerAvatar}`} src={user.avatar} fallback={initials(`${user.first_name} ${user.last_name}`.trim() || user.email)} size={32} />
          <CommentInput
            id={composerId}
            members={members}
            aria-label="Write a comment"
            placeholder="Write a comment…"
            aria-invalid={draftLength > commentLimit}
            rows={2}
            value={draft}
            disabled={pending === "post"}
            onValueChange={(body) => { setDraft(body); setPostError(""); }}
          />
          <span className={`${taskStyles.counter} ${styles.composerCounter}`}>{draftLength} / {commentLimit}</span>
          <button className={`${taskStyles.primaryButton} ${styles.send}`} aria-label="Post comment" disabled={!canPost}>
            <span>Comment</span>
            <Image src="/icons/comments/send.svg" alt="" width={20} height={20} />
          </button>
          <div className={styles.attachmentControls}>
            <label className={styles.attachment}>
              Attach file
              <input type="file" accept=".png,.jpg,.jpeg,.txt" disabled={pending === "post"} onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (!file) return;
                if (!file.size || file.size > 5 * 1024 * 1024) {
                  setPostError("Choose a nonempty file up to 5 MB.");
                  return;
                }
                setAttachment(file);
                setPostError("");
              }} />
            </label>
            {attachment && (
              <button type="button" className={styles.attachment} onClick={() => setAttachment(undefined)} disabled={pending === "post"}>
                Remove {attachment.name}
              </button>
            )}
          </div>
        </form>
        {draftLength > commentLimit && <p className={styles.fieldError} role="alert">Comment cannot exceed 5000 characters.</p>}
      </div>
      {deleting && (
        <dialog
          ref={deleteDialog}
          className={styles.confirm}
          aria-labelledby={dialogTitle}
          aria-describedby={dialogDescription}
          onCancel={(event) => {
            event.preventDefault();
            if (!pending) closeDeleteDialog();
          }}
          onClick={(event) => {
            if (event.target === event.currentTarget && !pending) closeDeleteDialog();
          }}
        >
          <div className={styles.confirmContent}>
            <h3 id={dialogTitle}>Delete this comment?</h3>
            <p id={dialogDescription}>{deleting.author_name}’s comment will be permanently deleted. This can’t be undone.</p>
            <blockquote>
              <strong>{deleting.author_name}</strong>
              <p className={styles.body}>{deleting.body}</p>
            </blockquote>
            {deleteError && <p className={taskStyles.alert} role="alert">{deleteError}</p>}
            <div className={styles.confirmActions}>
              <button type="button" autoFocus className={taskStyles.secondaryButton} disabled={Boolean(pending)} onClick={closeDeleteDialog}>Cancel</button>
              <button type="button" className={taskStyles.dangerButton} disabled={Boolean(pending)} onClick={remove}>
                {pending === "delete" ? "Deleting…" : "Delete comment"}
              </button>
            </div>
          </div>
        </dialog>
      )}
    </div>
  );
}
