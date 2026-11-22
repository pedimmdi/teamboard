"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ApiError, chatWebSocketUrl, deleteChatMessage, downloadChatAttachment, editChatMessage,
  getChatMessage, getChatMessages, sendChatMessage, type ChatMessage, type WorkspaceMember,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useChatUnread } from "./chat-unread";
import Avatar from "@/components/ui/Avatar";
import ProjectDialog from "@/app/dashboard/workspaces/[slug]/projects/project-dialog";
import { mergeChatMessages, validateChatFiles } from "./chat-utils";
import styles from "./chats.module.css";

function messageError(error: unknown) {
  return (error instanceof ApiError && error.errors ? Object.values(error.errors).flat().join(" ") : "")
    || (error instanceof Error ? error.message : "Unable to complete this action.");
}

export default function ChatThread({ slug, conversation, title, members }: {
  slug: string; conversation: string; title: string; members: WorkspaceMember[];
}) {
  const { ui, formatDate, formatNumber } = useWorkspaceLocale();
  const { accessToken, user } = useAuth();
  const {markRead, refresh: refreshUnread} = useChatUnread();
  const [jumpTarget, setJumpTarget] = useState<string | null>(null);
  const [readRevision, setReadRevision] = useState(0);
  const [readError, setReadError] = useState(false);
  const lastAcknowledged = useRef<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [next, setNext] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [error, setError] = useState("");
  const [olderError, setOlderError] = useState("");
  const [actionError, setActionError] = useState("");
  const [revision, setRevision] = useState(0);
  const [connection, setConnection] = useState("Connecting…");
  const [content, setContent] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [reply, setReply] = useState<ChatMessage | null>(null);
  const [editing, setEditing] = useState<ChatMessage | null>(null);
  const [editText, setEditText] = useState("");
  const [deleting, setDeleting] = useState<ChatMessage | null>(null);
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const scrollToLatest = useRef(true);
  const changes = useRef(new Map<string, ChatMessage>());
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    let socket: WebSocket | undefined;
    let retry: ReturnType<typeof setTimeout>;
    let attempts = 0;
    const controller = new AbortController();

    async function synchronize(initial: boolean) {
      try {
        const page = await getChatMessages(accessToken!, slug, conversation, 1, controller.signal);
        if (cancelled) return;
        setMessages((current) => mergeChatMessages(initial ? [] : current,
          page.results.map((message) => changes.current.get(message.id) ?? message)));
        if (initial) {
          setNext(2);
          setHasMore(Boolean(page.next));
          setError("");
        }
      } catch (error) {
        if (!cancelled && (initial || (error instanceof ApiError && [401, 403, 404].includes(error.status)))) {
          setError(messageError(error));
          if (error instanceof ApiError && [401, 403, 404].includes(error.status)) setMessages([]);
        }
      } finally {
        if (!cancelled && initial) setLoading(false);
      }
    }

    function connect() {
      if (cancelled) return;
      socket = new WebSocket(chatWebSocketUrl(slug, conversation), ["jwt", accessToken!]);
      socket.onopen = () => {
        attempts = 0;
        setConnection("Live");
        void synchronize(false);
      };
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (!["message.created", "message.updated", "message.deleted"].includes(payload.type)) return;
          const message = payload.message as ChatMessage;
          if (message.conversation !== conversation || typeof message.id !== "string") return;
          if (payload.type !== "message.updated") refreshUnread();
          changes.current.set(message.id, message);
          setMessages((current) => mergeChatMessages(current, [message]));
        } catch {}
      };
      socket.onclose = (event) => {
        if (cancelled) return;
        setConnection("Reconnecting…");
        if ([4401, 4403, 4404].includes(event.code)) {
          setConnection("Live connection unavailable. Refresh to reconnect.");
          if ([4403, 4404].includes(event.code)) {
            setMessages([]);
            setError("This conversation is no longer available.");
          }
          return;
        }
        retry = setTimeout(connect, Math.min(30000, 1000 * 2 ** Math.min(attempts++, 5)));
      };
      socket.onerror = () => socket?.close();
    }

    void synchronize(true);
    connect();
    const poll = window.setInterval(() => {
      if (!document.hidden) void synchronize(false);
    }, 30000);
    const focus = () => { void synchronize(false); };
    window.addEventListener("focus", focus);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(poll);
      window.removeEventListener("focus", focus);
      clearTimeout(retry);
      socket?.close();
    };
  }, [accessToken, slug, conversation, revision, refreshUnread]);

  useEffect(() => {
    if (scrollToLatest.current) bottom.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length]);

  async function older() {
    if (!accessToken || loadingOlder) return;
    setLoadingOlder(true);
    setOlderError("");
    try {
      const page = await getChatMessages(accessToken, slug, conversation, next);
      setMessages((current) => mergeChatMessages(current,
        page.results.map((message) => changes.current.get(message.id) ?? message)));
      setNext(next + 1);
      setHasMore(Boolean(page.next));
    } catch (error) { setOlderError(messageError(error)); }
    finally { setLoadingOlder(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || busy || (!content.trim() && !files.length)) return;
    const validation = validateChatFiles(files);
    if (validation) { setActionError(validation); return; }
    setBusy(true); setActionError("");
    try {
      const message = await sendChatMessage(accessToken, slug, conversation, content, reply?.id ?? null, files);
      changes.current.set(message.id, message);
      scrollToLatest.current = true;
      setMessages((current) => mergeChatMessages(current, [message]));
      setContent(""); setFiles([]); setReply(null);
    } catch (error) { setActionError(messageError(error)); }
    finally { setBusy(false); }
  }

  async function saveEdit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !editing || busy) return;
    setBusy(true); setActionError("");
    try {
      const message = await editChatMessage(accessToken, slug, conversation, editing.id, editText);
      changes.current.set(message.id, message);
      setMessages((current) => mergeChatMessages(current, [message]));
      setEditing(null);
    } catch (error) { setActionError(messageError(error)); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!accessToken || !deleting || busy) return;
    setBusy(true); setActionError("");
    try {
      await deleteChatMessage(accessToken, slug, conversation, deleting.id);
      const message = { ...deleting, content: "", deleted_at: new Date().toISOString(), attachments: [] };
      changes.current.set(message.id, message);
      setMessages((current) => mergeChatMessages(current, [message]));
      setDeleting(null);
    } catch (error) { setActionError(messageError(error)); }
    finally { setBusy(false); }
  }

  async function download(message: ChatMessage, attachment: ChatMessage["attachments"][number]) {
    if (!accessToken) return;
    setActionError("");
    try {
      const blob = await downloadChatAttachment(accessToken, slug, conversation, message.id, attachment.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = attachment.filename; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setActionError(messageError(error)); }
  }

  async function jumpTo(id: string) {
    scrollToLatest.current = false;
    setActionError("");
    try {
      if (!messages.some((message) => message.id === id)) {
        if (!accessToken) return;
        const message = await getChatMessage(accessToken, slug, conversation, id);
        setMessages((current) => mergeChatMessages(current, [changes.current.get(id) ?? message]));
      }
      setJumpTarget(id);
    } catch (error) { setActionError(messageError(error)); }
  }

  useEffect(() => {
    if (!jumpTarget) return;
    const target = document.getElementById("chat-" + jumpTarget);
    if (!target) return;
    target.scrollIntoView({block: "center", behavior: "smooth"});
    target.animate([{background: "#e0e7ff"}, {background: "transparent"}], {duration: 1000});
    const frame = requestAnimationFrame(() => setJumpTarget(null));
    return () => cancelAnimationFrame(frame);
  }, [jumpTarget, messages]);

  useEffect(() => {
    const visible = () => {if (!document.hidden) setReadRevision((value) => value + 1);};
    window.addEventListener("focus", visible);
    document.addEventListener("visibilitychange", visible);
    return () => {window.removeEventListener("focus", visible); document.removeEventListener("visibilitychange", visible);};
  }, []);

  useEffect(() => {
    const latest = messages.at(-1);
    if (!latest || document.hidden || !scrollToLatest.current || latest.id === lastAcknowledged.current) return;
    const timer = window.setTimeout(() => {
      void markRead(conversation, latest.id).then(() => {lastAcknowledged.current = latest.id; setReadError(false);})
        .catch(() => setReadError(true));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [messages, conversation, markRead, readRevision]);

  return (
    <section className={styles.thread} aria-label={title}>
      <header className={styles.threadHeader}><h3><bdi>{title}</bdi></h3><span>{ui(connection)}</span>
        {connection !== "Live" && <button onClick={() => setRevision((value) => value + 1)}>{ui("Reconnect")}</button>}
      </header>
      {readError && <p className={styles.error} role="alert">{ui("Unable to mark messages as read.")} <button onClick={() => setReadRevision((value) => value + 1)}>{ui("Retry read status")}</button></p>}
      <div className={styles.messages} role="log" aria-label={ui("Messages")} aria-live="polite" onScroll={(event) => {
        const element = event.currentTarget;
        const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 100;
        if (atBottom && !scrollToLatest.current) setReadRevision((value) => value + 1);
        scrollToLatest.current = atBottom;
      }}>
        {loading ? <p role="status">{ui("Loading messages…")}</p> : error ? <div role="alert"><p>{ui(error)}</p>
          <button onClick={() => setRevision((value) => value + 1)}>{ui("Try again")}</button></div> : <>
          {hasMore && <button disabled={loadingOlder} onClick={() => void older()}>{loadingOlder ? ui("Loading…") : ui("Load earlier messages")}</button>}
          {olderError && <p role="alert">{ui(olderError)}</p>}
          {!messages.length && <div className={styles.empty}><h3>{ui("Start the conversation")}</h3><p>{ui("Share an update or ask your team a question.")}</p></div>}
          {messages.map((message) => {
            const member = members.find((member) => member.user_id === message.sender_id);
            const parent = messages.find((parent) => parent.id === message.reply_to);
            return <article key={message.id} id={"chat-" + message.id} className={styles.message} data-own={message.sender_id === user?.id}>
              <Avatar className={styles.avatar} src={member?.avatar ?? null} fallback={(member?.user_email ?? "?").charAt(0).toUpperCase()} size={30} />
              <div className={styles.messageBody}>
                <header><strong>{member?.user_email ?? (message.sender_id === null ? ui("Deleted user") : ui("Former member"))}</strong>
                  <time dateTime={message.created_at}>{formatDate(message.created_at, { dateStyle: "medium", timeStyle: "short" })}</time>
                  {message.edited_at && !message.deleted_at && <span>{ui("Edited")}</span>}
                </header>
                {message.reply_to && <button className={styles.replyPreview} onClick={() => void jumpTo(message.reply_to!)}>
                  {ui("Reply to")} {parent?.deleted_at ? ui("deleted message") : parent?.content || ui("earlier message")}
                </button>}
                <p dir="auto">{message.deleted_at ? ui("Message deleted") : message.content}</p>
                {message.attachments.map((attachment) => <button key={attachment.id} className={styles.attachment}
                  onClick={() => void download(message, attachment)}>{attachment.filename} · {formatNumber(Math.ceil(attachment.size / 1024))} {ui("KB")}</button>)}
                {!message.deleted_at && <div className={styles.messageActions}>
                  <button onClick={() => setReply(message)}>{ui("Reply")}</button>
                  {message.sender_id === user?.id && <>
                    <button onClick={() => { setActionError(""); setEditing(message); setEditText(message.content); }}>{ui("Edit")}</button>
                    <button onClick={() => { setActionError(""); setDeleting(message); }}>{ui("Delete")}</button>
                  </>}
                </div>}
              </div>
            </article>;
          })}
        </>}
        <div ref={bottom} />
      </div>
      <form className={styles.composer} onSubmit={submit}>
        {reply && <div className={styles.replying}>{ui("Replying to")} {reply.content.slice(0, 100) || ui("attachment")}
          <button type="button" onClick={() => setReply(null)}>{ui("Cancel reply")}</button></div>}
        {actionError && !editing && !deleting && <p role="alert" className={styles.error}>{ui(actionError)}</p>}
        <label className={styles.srOnly} htmlFor={"message-" + conversation}>{ui("Write a message")}</label>
        <textarea id={"message-" + conversation} dir={content ? "auto" : undefined} placeholder={ui("Write a message…")} maxLength={5000} rows={2}
          value={content} disabled={busy || loading || Boolean(error)} onChange={(event) => setContent(event.target.value)} />
        {files.map((file, index) => <div className={styles.file} key={index}>{file.name}
          <button type="button" disabled={busy} aria-label={ui("Remove {0}", file.name)} onClick={() => setFiles((current) => current.filter((_, position) => position !== index))}>×</button></div>)}
        <div className={styles.composerActions}>
          <input ref={fileInput} aria-label={ui("Attach chat files")} type="file" multiple accept=".txt,.png,.jpg,.jpeg" hidden onChange={(event) => {
            const selected = [...files, ...Array.from(event.target.files ?? [])];
            event.target.value = "";
            const validation = validateChatFiles(selected);
            setActionError(validation);
            if (!validation) setFiles(selected);
          }} />
          <button type="button" disabled={busy} onClick={() => fileInput.current?.click()}>{ui("Attach files")}</button>
          <small>{formatNumber(content.length)} / {formatNumber(5000)} · TXT, PNG, JPEG</small>
          <button className={styles.primary} disabled={busy || loading || Boolean(error) || (!content.trim() && !files.length)}>{busy ? ui("Sending…") : ui("Send message")}</button>
        </div>
      </form>
      {editing && <ProjectDialog title={ui("Edit message")} onClose={() => setEditing(null)} busy={busy}>
        <form className={styles.dialogForm} onSubmit={saveEdit}>
          {actionError && <p role="alert">{ui(actionError)}</p>}
          <label>{ui("Message")}<textarea dir={editText ? "auto" : undefined} required={!editing.attachments.length} maxLength={5000} rows={4} value={editText} onChange={(event) => setEditText(event.target.value)} /></label>
          <button disabled={busy} className={styles.primary}>{ui("Save message")}</button>
        </form>
      </ProjectDialog>}
      {deleting && <ProjectDialog title={ui("Delete message?")} onClose={() => setDeleting(null)} busy={busy}>
        <p>{ui("The message and its attachments will be removed.")}</p>
        {actionError && <p role="alert">{ui(actionError)}</p>}
        <button disabled={busy} onClick={() => void remove()}>{ui("Delete message")}</button>
      </ProjectDialog>}
    </section>
  );
}
