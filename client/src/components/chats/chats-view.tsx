"use client";

import { useEffect, useState } from "react";
import {
  ApiError, getDirectChats, getProjectChat, getProjects, getWorkspaceMembers, startDirectChat,
  type ChatConversation, type Project, type WorkspaceMember,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import ChatThread from "./chat-thread";
import ChatIcon from "./chat-icon";
import styles from "./chats.module.css";

export default function ChatsView({ slug, projectId }: { slug: string; projectId?: string }) {
  const { accessToken, user } = useAuth();
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
      if (!projectId) {
        for (let page = 1; !cancelled; page++) {
          const response = await getProjects(accessToken!, slug, page);
          projects.push(...response.results);
          if (!response.next) break;
        }
      }
      const [direct, projectChat] = await Promise.all([
        projectId ? Promise.resolve([]) : getDirectChats(accessToken!, slug),
        projectId ? getProjectChat(accessToken!, slug, projectId) : Promise.resolve(undefined),
      ]);
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

  const thread = projectId && data?.projectChat ? { conversation: data.projectChat, title: "Project chat" } : selected;
  const query = search.toLowerCase();
  return (
    <section className={styles.chats} aria-label="Chats">
      <header className={styles.heading}><span className={styles.icon}><ChatIcon /></span><div><h2>Chats</h2><p>Conversations with your team</p></div></header>
      {error && <div role="alert" className={styles.error}><p>{error}</p><button onClick={() => setRevision((value) => value + 1)}>Try again</button></div>}
      {!data ? !error && <p role="status">Loading chats…</p> : (
        <div className={projectId ? undefined : styles.layout} data-selected={Boolean(thread)}>
          {!projectId && <aside className={styles.sidebar} aria-label="Conversations">
            <label>Find a conversation<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Project or teammate…" /></label>
            <h3>Projects</h3>
            {!data.projects.length && <p>No accessible projects.</p>}
            {data.projects.filter((project) => project.name.toLowerCase().includes(query)).map((project) => <button
              key={project.id} disabled={opening} aria-pressed={thread?.conversation.project === project.id}
              onClick={() => void openProject(project)}>{project.name}</button>)}
            <h3>Direct messages</h3>
            {data.direct.map((conversation) => {
              const recipient = conversation.direct_user_low === user?.id ? conversation.direct_user_high : conversation.direct_user_low;
              const title = data.members.find((member) => member.user_id === recipient)?.user_email ?? "Former member";
              return title.toLowerCase().includes(query) && <button key={conversation.id} aria-pressed={thread?.conversation.id === conversation.id}
                onClick={() => setSelected({ conversation, title })}>{title}</button>;
            })}
            <h3>Start a conversation</h3>
            {data.members.filter((member) => member.user_id !== user?.id && member.user_email.toLowerCase().includes(query)).map((member) =>
              <button key={member.id} disabled={opening} onClick={() => void direct(member)}>{member.user_email}</button>)}
          </aside>}
          <div className={styles.threadArea}>
            {!projectId && thread && <button className={styles.back} onClick={() => setSelected(null)}>← Conversations</button>}
            {thread ? <ChatThread key={thread.conversation.id} slug={slug} conversation={thread.conversation.id} title={thread.title} members={data.members} /> : (
              <div className={styles.empty}><ChatIcon /><h3>Your team conversations</h3><p>Choose a project or start a direct message with a teammate.</p></div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
