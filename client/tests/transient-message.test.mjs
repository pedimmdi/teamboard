import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import ts from "typescript";

test("temporary feedback resets its timer for repeated messages and cleans up on unmount", async () => {
  const dom = new JSDOM("<main></main>");
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const pending = new Map();
  let sequence = 0;
  const exports = {};
  runInNewContext(ts.transpileModule(readFileSync(new URL(
    "../src/hooks/use-transient-message.ts", import.meta.url,
  ), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
    exports, require: () => React,
    setTimeout: (callback, delay) => { assert.equal(delay, 5000); pending.set(++sequence, callback); return sequence; },
    clearTimeout: (id) => pending.delete(id),
  });
  let update;
  function Feedback() {
    const [message, setMessage] = exports.useTransientMessage("");
    update = setMessage;
    return React.createElement("p", null, message);
  }
  const { createRoot } = await import("react-dom/client");
  const root = createRoot(document.querySelector("main"));
  try {
    await act(async () => root.render(React.createElement(Feedback)));
    await act(async () => update("Saved"));
    const first = sequence;
    await act(async () => update("Saved"));
    assert.equal(pending.has(first), false);
    assert.equal(pending.size, 1);
    await act(async () => {
      const [id, callback] = pending.entries().next().value;
      pending.delete(id);
      callback();
    });
    assert.equal(document.querySelector("p").textContent, "");
    await act(async () => update("New feedback"));
  } finally {
    await act(async () => root.unmount());
    assert.equal(pending.size, 0);
    dom.window.close();
  }
});
