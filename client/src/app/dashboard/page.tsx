"use client";
import {useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import {useAuth} from "@/lib/auth";
import {dashboardWorkspaceKey, loadDashboardWorkspace} from "./dashboard-workspace";
export default function DashboardEntry() {
 const {accessToken,user}=useAuth(); const router=useRouter(); const [error,setError]=useState(""); const [retry,setRetry]=useState(0);
 useEffect(()=>{if(!accessToken||!user)return;let cancelled=false;let saved:string|null=null;
 try{saved=localStorage.getItem(dashboardWorkspaceKey(user.id)) || sessionStorage.getItem(dashboardWorkspaceKey(user.id));}catch{}
 loadDashboardWorkspace(accessToken,undefined,saved).then(w=>{if(!cancelled)router.replace(w?`/dashboard/workspaces/${encodeURIComponent(w.slug)}/dashboard`:"/dashboard/workspaces");}).catch(()=>{if(!cancelled)setError("Unable to select your workspace.");});
 return()=>{cancelled=true;};},[accessToken,user,router,retry]);
 return error?<div role="alert">{error}<button onClick={()=>{setError("");setRetry(v=>v+1);}}>Try again</button></div>:<p role="status">Opening your dashboard…</p>;
}
