"use client";

import { useWorkspaceLocale } from "@/lib/workspace-locale";
import { useEffect, useState } from "react";
import {
  ApiError, getDirectChats, getProjectChat, getProjects, getWorkspaceMembers, startDirectChat,
  type ChatConversation, type Project, type WorkspaceMember,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ChatUnreadBadge, useChatUnread } from "./chat-unread";
import ChatThread from "./chat-thread";
import ChatIcon from "./chat-icon";
import styles from "./chats.module.css";

export default function ChatsView({ slug, projectId }: { slug: string; projectId?: string }) {
  const { ui } = useWorkspaceLocale();
  const { accessToken, user } = useAuth();
  const {summary, failed, refresh} = useChatUnread();
  const [result, setResult] = useState<{ key: string; projects: Project[]; members: WorkspaceMember[]; direct: ChatConversation[]; projectChat?: ChatConversation }>();
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<{ conversation: ChatConversation; title: string } | null>(null);
  const [opening, setOpening] = useState(false);
  const [search, setSearch] = useState("");
  const key = JSON.stringify([slug, projectId]);
  const data = result?.key === key ? result : undefined;

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    async function load() {
      const members: WorkspaceMember[] = [];
      for (let page = 1; !cancelled; page++) {
        const response = await getWorkspaceMembers(accessToken!, slug, page);
        members.push(...response.results);
        if (!response.next) break;
      }
      const projects: Project[] = [];
      const direct: ChatConversation[] = [];
      if (!projectId) {
        for (let page = 1; !cancelled; page++) {
          const response = await getProjects(accessToken!, slug, page);
          projects.push(...response.results);
          if (!response.next) break;
        }
        for (let page = 1; !cancelled; page++) {
          const response = await getDirectChats(accessToken!, slug, page);
          direct.push(...response.results);
          if (!response.next) break;
        }
      }
      const projectChat = projectId && !cancelled
        ? await getProjectChat(accessToken!, slug, projectId)
        : undefined;
      if (!cancelled) {
        setResult({ key, members, projects, direct, projectChat });
        setError("");
      }
    }
    void load().catch((error: unknown) => {
      if (!cancelled) setError(error instanceof Error ? error.message : "Unable to load chats.");
    });
    return () => { cancelled = true; };
  }, [accessToken, slug, projectId, key, revision]);

  async function openProject(project: Project) {
    if (!accessToken || opening) return;
    setOpening(true); setError("");
    try {
      const conversation = await getProjectChat(accessToken, slug, project.id);
      setSelected({ conversation, title: project.name });
    } catch (error) { setError(error instanceof Error ? error.message : "Unable to open chat."); }
    finally { setOpening(false); }
  }
  async function direct(member: WorkspaceMember) {
    if (!accessToken || opening) return;
    setOpening(true); setError("");
    try {
      const conversation = await startDirectChat(accessToken, slug, member.user_id);
      setSelected({ conversation, title: member.user_email });
      setResult((current) => current ? { ...current, direct: [conversation, ...current.direct.filter((item) => item.id !== conversation.id)] } : current);
    } catch (error) {
      setError(error instanceof ApiError ? error.message : "Unable to start a conversation.");
    } finally { setOpening(false); }
  }

  const thread = projectId && data?.projectChat ? { conversation: data.projectChat, title: ui("Project chat") } : selected;
  const query = search.toLowerCase();
  return (
    <section className={styles.chats} aria-label={ui("Chats")}>
      <header className={styles.heading}><span className={styles.icon}><ChatIcon /></span><div><h2>{ui("Chats")}</h2><p>{ui("Conversations with your team")}</p></div></header>
      {failed && <p className={styles.error} role="alert">{ui("Unable to refresh unread counts.")} <button onClick={refresh}>{ui("Retry unread counts")}</button></p>}
      {error && <div role="alert" className={styles.error}><p>{ui(error)}</p><button onClick={() => setRevision((value) => value + 1)}>{ui("Try again")}</button></div>}
      {!data ? !error && <p role="status">{ui("Loading chats…")}</p> : (
        <div className={projectId ? undefined : styles.layout} data-selected={Boolean(thread)}>
          {!projectId && <aside className={styles.sidebar} aria-label={ui("Conversations")}>
            <label>{ui("Find a conversation")}<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={ui("Project or teammate…")} /></label>
            <h3>{ui("Projects")}</h3>
            {!data.projects.length && <p>{ui("No accessible projects.")}</p>}
            {data.projects.filter((project) => project.name.toLowerCase().includes(query)).map((project) => <button
              key={project.id} disabled={opening} aria-pressed={thread?.conversation.project === project.id}
              onClick={() => void openProject(project)}><span>{project.name}</span><ChatUnreadBadge count={summary.conversations.find((item) => item.project === project.id)?.unread_count ?? 0} /></button>)}
            <h3>{ui("Direct messages")}</h3>
            {data.members.filter((member) => member.user_id !== user?.id && member.user_email.toLowerCase().includes(query)).map((member) =>
              <button key={member.id} disabled={opening}
                aria-pressed={Boolean(thread?.conversation.type === "direct" &&
                  [thread.conversation.direct_user_low, thread.conversation.direct_user_high].includes(member.user_id))}
                onClick={() => {
                  const existing = data.direct.find((conversation) =>
                    [conversation.direct_user_low, conversation.direct_user_high].includes(member.user_id));
                  if (existing) setSelected({ conversation: existing, title: member.user_email });
                  else void direct(member);
                }}><span>{member.user_email}</span><ChatUnreadBadge count={summary.conversations.find((item) => item.recipient_id === member.user_id)?.unread_count ?? 0} /></button>)}
            {data.direct.filter((conversation) => {
              const recipient = conversation.direct_user_low === user?.id ? conversation.direct_user_high : conversation.direct_user_low;
              return !data.members.some((member) => member.user_id === recipient);
            }).filter(() => ui("Former member").toLowerCase().includes(query)).map((conversation) =>
              <button key={conversation.id} aria-pressed={thread?.conversation.id === conversation.id}
                onClick={() => setSelected({conversation, title: ui("Former member")})}><span>{ui("Former member")}</span><ChatUnreadBadge count={summary.conversations.find((item) => item.id === conversation.id)?.unread_count ?? 0} /></button>)}
          </aside>}
          <div className={styles.threadArea}>
            {!projectId && thread && <button className={styles.back} onClick={() => setSelected(null)}>{ui("← Conversations")}</button>}
            {thread ? <ChatThread key={thread.conversation.id} slug={slug} conversation={thread.conversation.id} title={thread.title} members={data.members} /> : (
              <div className={styles.empty}><ChatIcon /><h3>{ui("Your team conversations")}</h3><p>{ui("Choose a project or start a direct message with a teammate.")}</p></div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
