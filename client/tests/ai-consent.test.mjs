import assert from "node:assert/strict";
import test from "node:test";

import { loadSource } from "./load-source.mjs";

const { getAiCallback, getAiConsentInteraction, getAiConsentReturn, getLocalAiCallback, getTaskDeletionApproval } =
  loadSource("../src/lib/ai-consent.ts", { URL });

test("AI consent returns only to the fixed route with a canonical interaction ID", () => {
  const id = "12345678-1234-4234-9234-123456789abc";
  assert.equal(getAiConsentInteraction(`#interaction=${id}`), id);
  assert.equal(getAiConsentReturn(`#ai=${id}`), `/ai/authorize#interaction=${id}`);
  for (const value of ["#ai=//external.invalid", `#ai=${id}&next=//external.invalid`, "#ai=123", "#invitation=42"]) {
    assert.equal(getAiConsentReturn(value), null);
  }
});

test("AI return paths bind a task approval and verify the registered hosted callback", () => {
  const id = "12345678-1234-4234-9234-123456789abc";
  assert.equal(getTaskDeletionApproval(`#approval=${id}`), id);
  assert.equal(getTaskDeletionApproval(`#approval=${id}&role=admin`), null);
  assert.equal(getAiConsentReturn(`#approve-task=${id}`), `/ai/approve-task-deletion#approval=${id}`);
  const registered = "https://provider.example.com/connect?tenant=42";
  assert.equal(getAiCallback(`${registered}&code=opaque`, registered), `${registered}&code=opaque`);
  assert.equal(getAiCallback("https://provider.example.com/connect?tenant=43", registered), null);
  assert.equal(getAiCallback("https://another.example.com/connect?tenant=42", registered), null);
});

test("consent accepts only absolute loopback HTTP callbacks on a known port", () => {
  const callback = "http://127.0.0.1:6274/callback?state=test";
  assert.equal(getLocalAiCallback(callback), callback);
  for (const value of ["", "/dashboard", "https://example.invalid/callback", "http://user@localhost:6274/callback",
    "http://localhost/callback", "http://localhost:6274/callback#token", "http://127.0.0.1.example.invalid:6274/callback"]) {
    assert.equal(getLocalAiCallback(value), null);
  }
});
