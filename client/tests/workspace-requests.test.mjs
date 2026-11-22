import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
import ts from "typescript";
test("workspace reads share in-flight requests only, isolated by token and slug",async()=>{
 const exports={},calls=[],replies=[];
 const source=ts.transpileModule(readFileSync(new URL("../src/lib/api.ts",import.meta.url),"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 runInNewContext(source,{exports,process:{env:{}},FormData,URLSearchParams,fetch:(url)=>{calls.push(url);return new Promise(resolve=>replies.push(()=>resolve(new Response('{}',{headers:{"Content-Type":"application/json"}}))));}});
 const a=exports.getWorkspace("one","team");
 assert.equal(exports.getWorkspace("one","team"),a);
 const b=exports.getWorkspace("two","team"),c=exports.getWorkspace("one","other");
 assert.notEqual(a,b);assert.notEqual(a,c);assert.equal(calls.length,3);
 replies.splice(0).forEach(reply=>reply());await Promise.all([a,b,c]);
 const fresh=exports.getWorkspace("one","team");assert.equal(calls.length,4);
 replies.splice(0).forEach(reply=>reply());await fresh;
});
