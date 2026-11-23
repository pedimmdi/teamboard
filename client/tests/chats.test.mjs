import assert from "node:assert/strict";
import { loadSource } from "./load-source.mjs";
import test from "node:test";


test("chat merging deduplicates live events and preserves chronological history", () => {
  const { mergeChatMessages, validateChatFiles } = loadSource("../src/components/chats/chat-utils.ts");
  const first = { id: "1", created_at: "2026-11-01T00:00:00Z", content: "First" };
  const second = { id: "2", created_at: "2026-11-01T00:01:00Z", content: "Second" };
  const result = mergeChatMessages([second], [first, { ...second, content: "Edited" }]);
  assert.equal(result.length, 2);
  assert.equal(result[0].id, "1");
  assert.equal(result[1].content, "Edited");
  assert.equal(validateChatFiles([{ name: "notes.txt", size: 10 }]), "");
  assert.match(validateChatFiles([{ name: "unsafe.exe", size: 10 }]), /TXT/);
  assert.match(validateChatFiles(Array(6).fill({ name: "image.png", size: 10 })), /five/);
  assert.match(validateChatFiles([{ name: "notes.txt", size: 0 }]), /nonempty/);
});

test("chat client authenticates REST, sends replies and attachments, and keeps JWTs out of URLs", async () => {
  const calls = [];
  const api = loadSource("../src/lib/api.ts", {
    process: { env: { NEXT_PUBLIC_API_URL: "https://api.example.com" } },
    FormData, URLSearchParams, URL,
    fetch: async (url, options) => {
      calls.push([url, options]);
      return new Response("{}", { headers: { "Content-Type": "application/json" } });
    },
  });
  await api.getProjectChat("token", "work", "project");
  await api.startDirectChat("token", "work", 2);
  await api.getChatMessages("token", "work", "conversation", 2);
  await api.sendChatMessage("token", "work", "conversation", "Reply", "parent", [
    new File(["notes"], "notes.txt", { type: "text/plain" }),
  ]);
  await api.editChatMessage("token", "work", "conversation", "message", "Changed");
  await api.deleteChatMessage("token", "work", "conversation", "message");
  assert.equal(calls[0][0], "https://api.example.com/api/v1/workspaces/work/projects/project/chat/");
  assert.equal(JSON.parse(calls[1][1].body).recipient_id, 2);
  assert.match(calls[2][0], /page=2$/);
  assert.equal(calls[3][1].body.get("reply_to"), "parent");
  assert.equal(calls[3][1].body.get("attachments").name, "notes.txt");
  assert.equal(calls[4][1].method, "PATCH");
  assert.equal(calls[5][1].method, "DELETE");
  for (const [, options] of calls) assert.equal(options.headers.Authorization, "Bearer token");
  assert.equal(api.chatWebSocketUrl("work", "conversation"), "wss://api.example.com/ws/chats/work/conversation/");
});


test("unread and parent retrieval APIs keep workspace/conversation boundaries and read cursor payload", async () => {
  const calls = [];
  const api = loadSource("../src/lib/api.ts", {
    process: {env: {NEXT_PUBLIC_API_URL: "https://api.example.com"}}, URLSearchParams, FormData,
    fetch: async (url, options) => {calls.push([url, options]); return new Response("{}", {headers: {"Content-Type": "application/json"}});},
  });
  await api.getUnreadChats("token", "a/b");
  await api.markChatRead("token", "a/b", "conversation", "message");
  await api.getChatMessage("token", "a/b", "conversation", "parent");
  assert.match(calls[0][0], /workspaces\/a%2Fb\/chats\/unread\/$/);
  assert.match(calls[1][0], /chats\/conversation\/read\/$/);
  assert.equal(calls[1][1].method, "POST");
  assert.deepEqual(JSON.parse(calls[1][1].body), {message_id: "message"});
  assert.match(calls[2][0], /chats\/conversation\/messages\/parent\/$/);
  for (const [, options] of calls) assert.equal(options.headers.Authorization, "Bearer token");
});
