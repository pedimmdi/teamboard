import test from "node:test";
import assert from "node:assert/strict";
import { loadSource } from "./load-source.mjs";
test("workspace reads share in-flight requests only, isolated by token and slug",async()=>{
 const calls=[],replies=[];
 const exports=loadSource("../src/lib/api.ts",{process:{env:{}},FormData,URLSearchParams,fetch:(url)=>{calls.push(url);return new Promise(resolve=>replies.push(()=>resolve(new Response('{}',{headers:{"Content-Type":"application/json"}}))));}});
 const a=exports.getWorkspace("one","team");
 assert.equal(exports.getWorkspace("one","team"),a);
 const b=exports.getWorkspace("two","team"),c=exports.getWorkspace("one","other");
 assert.notEqual(a,b);assert.notEqual(a,c);assert.equal(calls.length,3);
 replies.splice(0).forEach(reply=>reply());await Promise.all([a,b,c]);
 const fresh=exports.getWorkspace("one","team");assert.equal(calls.length,4);
 replies.splice(0).forEach(reply=>reply());await fresh;
});
