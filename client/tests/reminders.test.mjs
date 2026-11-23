import assert from "node:assert/strict";
import test from "node:test";
import { loadSource } from "./load-source.mjs";
const utils=loadSource("../src/app/dashboard/workspaces/[slug]/projects/[projectId]/tasks/reminder-utils.ts",{Intl,Date,Set});
test("reminder wall clocks convert to UTC and round-trip in selected IANA zones",()=>{
  for(const [zone,input,expected] of [["Asia/Tehran","2030-06-01T09:00","2030-06-01T05:30:00.000Z"],["America/New_York","2030-06-01T09:00","2030-06-01T13:00:00.000Z"],["UTC","2030-06-01T09:00","2030-06-01T09:00:00.000Z"],["Asia/Kathmandu","2030-06-01T09:00","2030-06-01T03:15:00.000Z"]]) {
    assert.equal(utils.reminderLocalToUTC(input,zone),expected);assert.equal(utils.reminderLocalInput(expected,zone),input);
  }
});
test("reminder conversion rejects DST gaps, folds and malformed dates rather than shifting them",()=>{
  for(const input of ["2030-03-31T02:30","2030-10-27T02:30","2030-02-31T09:00","invalid"]) assert.throws(()=>utils.reminderLocalToUTC(input,"Europe/Paris"));
  assert.throws(()=>utils.reminderLocalToUTC("2030-06-01T09:00","Invalid/Zone"));
  assert.throws(()=>utils.futureReminderTime("2020-06-01T09:00","UTC"), /future/);
  assert.equal(utils.futureReminderTime("2030-06-01T09:00","UTC"), "2030-06-01T09:00:00.000Z");
});
test("private reminder client keeps scope, method and UTC data without recipient controls",async()=>{
  const calls=[];
  const api=loadSource("../src/lib/api.ts",{process:{env:{NEXT_PUBLIC_API_URL:"https://api.example.com"}},FormData,URLSearchParams,fetch:async(url,options)=>{calls.push([url,options]);return new Response("{}",{headers:{"Content-Type":"application/json"}});}});
  await api.getTaskReminders("token","team","project","task",2);
  await api.saveTaskReminder("token","team","project","task",{kind:"relative",timezone:"Asia/Tehran",days_before:1,local_time:"09:00"});
  await api.saveTaskReminder("token","team","project","task",{kind:"absolute",timezone:"UTC",run_at:"2030-06-01T09:00:00Z"},"reminder");
  await api.cancelTaskReminder("token","team","project","task","reminder");
  assert.match(calls[0][0],/tasks\/task\/reminders\/\?page=2$/);assert.equal(calls[1][1].method,"POST");assert.equal(calls[2][1].method,"PATCH");assert.equal(calls[3][1].method,"DELETE");
  assert.equal(JSON.parse(calls[1][1].body).timezone,"Asia/Tehran");
  for(const [,options] of calls)assert.equal(options.headers.Authorization,"Bearer token");
});
