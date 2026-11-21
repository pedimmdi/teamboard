import {apiFetch, type InboxNotification} from "./api";
export type DashboardItem = {id:string; title?:string; name?:string; task_title?:string; project?:string; task?:string; project_name?:string; due_date?:string; run_at?:string; starts_at?:string};
export type DashboardSection = {count:number; items:DashboardItem[]; unread_count?:number};
export type WorkspaceDashboard = {workspace_name:string; today_tasks_count:number; as_of:string; due_soon_until:string; upcoming_until:string; my_tasks:DashboardSection; follow_up:DashboardSection; overdue_tasks:DashboardSection; due_soon_tasks:DashboardSection; completed_tasks:DashboardSection; projects:DashboardSection; upcoming_reminders:DashboardSection; upcoming_events:DashboardSection; recent_notifications:{count:number;unread_count:number;items:InboxNotification[]}};
const pending = new Map<string,Promise<WorkspaceDashboard>>();
export function getWorkspaceDashboard(token:string,slug:string) {
  const key=JSON.stringify([token,slug]);
  let request=pending.get(key);
  if (!request) {
    request=apiFetch<WorkspaceDashboard>(`/api/v1/workspaces/${encodeURIComponent(slug)}/dashboard/`,{token});
    pending.set(key,request);
    void request.finally(()=>pending.delete(key)).catch(()=>{});
  }
  return request;
}
