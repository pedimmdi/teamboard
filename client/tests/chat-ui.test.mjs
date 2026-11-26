import assert from "node:assert/strict";
import { loadSource } from "./load-source.mjs";
import test from "node:test";
import {JSDOM} from "jsdom";
import React, {act} from "react";
import {renderToStaticMarkup} from "react-dom/server";

function component(name, modules, globals = {}, locale = "en") {
  const styles = new Proxy({}, {get: (_, name) => name === "__esModule" ? false : String(name)});
  const region = locale === "fa" ? "fa-IR" : "en-US";
  const copy = loadSource("../src/lib/workspace-locale.ts", {require: () => ({
    useLocale: () => ({
      locale,
      formatDate: (value, options) => new Intl.DateTimeFormat(region, options).format(new Date(value)),
      formatNumber: (value) => new Intl.NumberFormat(region).format(value),
    }),
  })});
  return loadSource("../src/components/chats/" + name + ".tsx", {React, ...globals, require: (path) => path.endsWith(".css") ? styles : path === "react" ? React : path === "@/lib/workspace-locale" ? copy : modules[path]});
}

test("chat unread badges hide zero and show exact values through ten, then +10", () => {
  const {ChatUnreadBadge} = component("chat-unread", {});
  assert.equal(renderToStaticMarkup(React.createElement(ChatUnreadBadge, {count: 0})), "");
  for (const count of [1, 7, 10, 11, 50]) {
    const html = renderToStaticMarkup(React.createElement(ChatUnreadBadge, {count}));
    assert.ok(html.includes(`aria-label="${count} unread messages"`));
    assert.ok(html.includes(`>${count > 10 ? "+10" : count}</span>`));
  }
});

test("Persian chat unread badges display Persian numbers and a localized accessible name", () => {
  const {ChatUnreadBadge} = component("chat-unread", {}, {}, "fa");
  const html = renderToStaticMarkup(React.createElement(ChatUnreadBadge, {count: 12}));
  assert.ok(html.includes('aria-label="۱۲ پیام خوانده‌نشده"'));
  assert.ok(html.includes(">+۱۰</span>"));
});

test("the workspace chat list opens a former member's conversation from the next page", async () => {
  const dom = new JSDOM("<main></main>");
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const {createRoot} = await import("react-dom/client");
  const root = createRoot(document.querySelector("main"));
  const pages = [];
  const existing = {id: "existing", type: "direct", direct_user_low: 1, direct_user_high: 2};
  const former = {id: "former", type: "direct", direct_user_low: 1, direct_user_high: 3};
  const emptyPage = async () => ({next: null, results: []});
  const Stub = () => null;
  const Chats = component("chats-view", {
    "@/lib/api": {
      getWorkspaceMembers: async () => ({next: null, results: [{id: "member", user_id: 2, user_email: "member@example.com"}]}),
      getProjects: emptyPage,
      getDirectChats: async (token, slug, page) => {
        pages.push([token, slug, page]);
        return page === 1 ? {next: "page 2", results: [existing]} : {next: null, results: [former]};
      },
    },
    "@/lib/auth": {useAuth: () => ({accessToken: "token", user: {id: 1}})},
    "./chat-unread": {ChatUnreadBadge: Stub, useChatUnread: () => ({summary: {conversations: []}})},
    "./chat-thread": ({conversation}) => React.createElement("output", null, conversation),
    "./chat-icon": Stub,
  }).default;

  try {
    await act(async () => root.render(React.createElement(Chats, {slug: "team"})));
    assert.deepEqual(pages, [["token", "team", 1], ["token", "team", 2]]);
    const button = [...document.querySelectorAll("button")].find((item) => item.textContent === "Former member");
    assert.ok(button);
    await act(async () => button.click());
    assert.equal(document.querySelector("output").textContent, "former");
  } finally {
    await act(async () => root.unmount());
    dom.window.close();
    delete globalThis.window;
    delete globalThis.document;
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
});

test("reply navigation fetches an unloaded parent, scrolls and briefly highlights it, then reuses the loaded message", async () => {
  const dom = new JSDOM("<main></main>", {pretendToBeVisual: true});
  globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const {createRoot} = await import("react-dom/client");
  const root = createRoot(document.querySelector("main"));
  const calls = [];
  dom.window.HTMLElement.prototype.scrollIntoView = function () {if (this.id) calls.push(this.id);};
  dom.window.HTMLElement.prototype.animate = function (_, options) {calls.push(options.duration);};
  const parent = {id: "parent", conversation: "room", sender_id: 2, content: "Original message", created_at: "2026-11-01T00:00:00Z", attachments: [], deleted_at: null, reply_to: null};
  const reply = {...parent, id: "reply", content: "A reply", created_at: "2026-11-02T00:00:00Z", reply_to: "parent"};
  let fetches = 0;
  const api = {getChatMessages: async () => ({results: [reply], next: "page2"}), getChatMessage: async () => {fetches++; if (fetches === 1) throw new Error("Temporary failure"); return parent;}, chatWebSocketUrl: () => "wss://example.com", ApiError: class extends Error {}};
  const utils = {mergeChatMessages: (current, incoming) => [...new Map([...current, ...incoming].map((message) => [message.id, message])).values()].sort((a,b) => a.created_at.localeCompare(b.created_at))};
  const Stub = () => null;
  const markRead = async () => {};
  const refresh = () => {};
  const Thread = component("chat-thread", {
    "@/lib/api": api, "@/lib/auth": {useAuth: () => ({accessToken: "token", user: {id: 1}})},
    "./chat-unread": {useChatUnread: () => ({markRead, refresh})},
    "@/components/ui/Avatar": Stub, "@/app/dashboard/workspaces/[slug]/projects/project-dialog": Stub,
    "./chat-utils": utils,
  }, {document, window, Intl, Date, AbortController, WebSocket: class {close() {}}, setTimeout, clearTimeout,
    requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window), cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window)}).default;
  try {
    await act(async () => root.render(React.createElement(Thread, {slug: "team", conversation: "room", title: "Chat", members: []})));
    const preview = () => [...document.querySelectorAll("button")].find((button) => button.textContent.startsWith("Reply to "));
    await act(async () => {preview().click();});
    assert.equal(fetches, 1);
    assert.ok(document.querySelector("[role=alert]"));
    assert.equal(document.getElementById("chat-parent"), null);
    await act(async () => {preview().click();});
    assert.equal(fetches, 2);
    assert.equal(document.querySelector("[role=alert]"), null);
    assert.ok(document.getElementById("chat-parent"));
    assert.deepEqual(calls, ["chat-parent", 1000]);
    await act(async () => {await new Promise((resolve) => dom.window.requestAnimationFrame(resolve));});
    await act(async () => {preview().click();});
    assert.equal(fetches, 2);
    assert.ok(!document.body.textContent.includes("Load earlier messages to view"));
    assert.equal(document.getElementById("chat-parent").hasAttribute("tabindex"), false);
  } finally {
    await act(async () => root.unmount()); dom.window.close();
    delete globalThis.window; delete globalThis.document; delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
});


test("unread provider retains counts on failure, retries, acknowledges reads, and isolates workspaces", async () => {
  const dom = new JSDOM("<main></main>", {pretendToBeVisual: true});
  globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const {createRoot} = await import("react-dom/client");
  const root = createRoot(document.querySelector("main"));
  let fail = false, count = 7;
  const reads = [];
  const api = {
    getUnreadChats: async (_, slug) => {if (fail) throw new Error("Offline"); return {unread_count: slug === "first" ? count : 0, conversations: []};},
    markChatRead: async (...args) => {reads.push(args); count = 0;},
  };
  const {ChatUnreadProvider, useChatUnread} = component("chat-unread", {"@/lib/api": api, "@/lib/auth": {useAuth: () => ({accessToken: "token", user: {id: 1}})}}, {window, document, AbortController});
  function Probe() {
    const {summary, failed, refresh, markRead} = useChatUnread();
    return React.createElement("section", null,
      React.createElement("output", null, `${summary.unread_count}:${failed}`),
      React.createElement("button", {onClick: refresh}, "Retry"),
      React.createElement("button", {onClick: () => void markRead("room", "last")}, "Read"));
  }
  const render = (slug) => root.render(React.createElement(ChatUnreadProvider, {slug}, React.createElement(Probe)));
  try {
    await act(async () => render("first"));
    assert.equal(document.querySelector("output").textContent, "7:false");
    fail = true;
    await act(async () => document.querySelector("button").click());
    assert.equal(document.querySelector("output").textContent, "7:true");
    fail = false;
    await act(async () => document.querySelector("button").click());
    assert.equal(document.querySelector("output").textContent, "7:false");
    await act(async () => document.querySelectorAll("button")[1].click());
    assert.deepEqual(reads, [["token", "first", "room", "last"]]);
    assert.equal(document.querySelector("output").textContent, "0:false");
    count = 7;
    await act(async () => document.querySelector("button").click());
    await act(async () => render("second"));
    assert.equal(document.querySelector("output").textContent, "0:false");
  } finally {
    await act(async () => root.unmount()); dom.window.close();
    delete globalThis.window; delete globalThis.document; delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  }
});
