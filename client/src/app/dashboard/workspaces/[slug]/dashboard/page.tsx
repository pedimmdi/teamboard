"use client";
import Link from "next/link";
import {useParams} from "next/navigation";
import {useEffect,useState} from "react";
import {useAuth} from "@/lib/auth";
import {getWorkspaceDashboard,type WorkspaceDashboard,type DashboardItem} from "@/lib/workspace-dashboard";
import {notificationContent} from "@/app/dashboard/notifications/notification-content";
import styles from "./overview.module.css";

const sections = [
  ["my_tasks","My Tasks","Active tasks assigned to you"],
  ["follow_up","Follow Up","Tasks you created for teammates"],
  ["overdue_tasks","Overdue","Active tasks past their due date"],
  ["due_soon_tasks","Due Soon","Tasks approaching their due date"],
  ["completed_tasks","Completed","Your completed tasks"],
  ["projects","Projects","Projects you can access"],
  ["upcoming_reminders","Reminders","Your upcoming private reminders"],
  ["upcoming_events","Calendar","Upcoming project events"],
] as const;
export default function WorkspaceDashboardPage() {
  const {slug}=useParams<{slug:string}>(); const {accessToken}=useAuth();
  const [result,setResult]=useState<{slug:string;data:WorkspaceDashboard}|null>(null);
  const [failure,setFailure]=useState<{slug:string;message:string}|null>(null);
  const [retry,setRetry]=useState(0); const [mode,setMode]=useState<"list"|"count">("list");
  useEffect(()=>{if(!accessToken)return;let cancelled=false;
    getWorkspaceDashboard(accessToken,slug).then(data=>{if(!cancelled){setResult({slug,data});setFailure(null);}}).catch(()=>{if(!cancelled)setFailure({slug,message:"Unable to load this workspace’s dashboard."});});
    return()=>{cancelled=true;};
  },[accessToken,slug,retry]);
  const data=result?.slug===slug?result.data:null;const error=failure?.slug===slug?failure.message:null;
  const base=`/dashboard/workspaces/${encodeURIComponent(slug)}`;
  function itemLink(key:string,item:DashboardItem) {
    if(key==="projects")return `${base}/projects/${item.id}/tasks`;
    if(key==="upcoming_events")return `${base}/projects/${item.project}/calendar`;
    return `${base}/projects/${item.project}/tasks?task=${encodeURIComponent(item.task??item.id)}`;
  }
  return <section className={styles.page} aria-label="Workspace dashboard">
    <header className={styles.header}><div><p className={styles.eyebrow}>WORKSPACE OVERVIEW</p><h1>Dashboard</h1><p>{data?.workspace_name??"Your workspace"} · Your work, at a glance.</p></div>
      <div className={styles.toggle} role="group" aria-label="Dashboard display"><button aria-pressed={mode==="list"} onClick={()=>setMode("list")}>Lists</button><button aria-pressed={mode==="count"} onClick={()=>setMode("count")}>Counts</button></div>
    </header>
    {error?<div role="alert" className={styles.card}><p>{error}</p><button onClick={()=>{setFailure(null);setRetry(v=>v+1);}}>Try again</button></div>:!data?<p role="status" className={styles.card}>Loading your dashboard…</p>:<>
      <p className={styles.note}>Task dates use UTC · Due soon through {data.due_soon_until} · Upcoming activity through {new Date(data.upcoming_until).toLocaleDateString()}</p>
      <div className={styles.grid}>{sections.map(([key,title,description])=>{const section=data[key];return <article className={styles.card} key={key} aria-label={title}>
        <header><h2>{title}</h2><strong className={styles.count}>{section.count.toLocaleString()}</strong></header><p className={styles.note}>{description}</p>
        {mode==="list"&&(section.items.length?<ul>{section.items.slice(0,5).map(item=><li key={item.id}><Link href={itemLink(key,item)}>{item.title??item.task_title??item.name}</Link><small>{[item.project_name,item.due_date?`Due ${item.due_date}`:null,item.run_at?new Date(item.run_at).toLocaleString():null,item.starts_at?new Date(item.starts_at).toLocaleString():null].filter(Boolean).join(" · ")}</small></li>)}</ul>:<p className={styles.empty}>Nothing here right now.</p>)}
        <Link className={styles.more} href={`${base}/${key==="upcoming_events"?"calendar":"projects"}`}>{key==="upcoming_events"?"Open calendar":"Browse projects"} →</Link>
      </article>;})}
      <article className={styles.card} aria-label="Notifications"><header><h2>Notifications</h2><strong className={styles.count}>{data.recent_notifications.unread_count}</strong></header><p className={styles.note}>Unread in this workspace · {data.recent_notifications.count} recent notifications</p>
        {mode==="list"&&(data.recent_notifications.items.length?<ul>{data.recent_notifications.items.slice(0,5).map(item=>{const content=notificationContent(item);return <li key={item.id}><Link href={content.href??"/dashboard/notifications"}>{content.title}</Link><small>{content.description}</small></li>;})}</ul>:<p className={styles.empty}>You’re all caught up.</p>)}<Link className={styles.more} href="/dashboard/notifications">Open inbox →</Link>
      </article></div>
    </>}
  </section>;
}
