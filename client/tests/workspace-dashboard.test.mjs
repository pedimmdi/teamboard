import test from "node:test";
import assert from "node:assert/strict";
import { loadSource } from "./load-source.mjs";
function client(fetcher) {
  return loadSource("../src/lib/workspace-dashboard.ts", { require: () => ({ apiFetch: fetcher }), Map, JSON }).getWorkspaceDashboard;
}
test("dashboard shares concurrent requests without sharing user or workspace scope",async()=>{
  const calls=[];let finish;
  const get=client((path,options)=>{calls.push([path,options.token]);return new Promise(resolve=>{finish=resolve;});});
  const first=get("user-a","workspace-a");
  assert.equal(get("user-a","workspace-a"),first);
  assert.notEqual(get("user-a","workspace-b"),first);
  assert.notEqual(get("user-b","workspace-a"),first);
  assert.equal(calls.length,3);
  assert.match(calls[0][0],/\/api\/v1\/workspaces\/workspace-a\/dashboard\/$/);
  finish({});
});
test("dashboard failures are retryable and responses are not cached",async()=>{
  let count=0;
  const get=client(()=>++count===1?Promise.reject(new Error("offline")):Promise.resolve({workspace_name:"Recovered"}));
  await assert.rejects(get("token","team"),/offline/);
  assert.equal((await get("token","team")).workspace_name,"Recovered");
  await get("token","team");
  assert.equal(count,3);
});
