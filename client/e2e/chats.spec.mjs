import { expect, test } from "@playwright/test";

test("direct messages update in two browsers and support private attachments on mobile", async ({ browser }) => {
  test.setTimeout(90_000);
  const first = await browser.newContext();
  const second = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const sender = await first.newPage();
  const recipient = await second.newPage();
  async function login(page, email) {
    await page.goto("http://localhost:" + (process.env.E2E_FRONTEND_PORT || "3100") + "/login");
    await page.getByLabel("Email address").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page).toHaveURL(/dashboard/);
    await page.goto("http://localhost:" + (process.env.E2E_FRONTEND_PORT || "3100") + "/dashboard/workspaces/chat-tests/chats");
  }
  try {
    await login(sender, "browser-test@example.com");
    await login(recipient, "browser-chat-teammate@example.com");
    await expect(sender.getByRole("button", { name: "browser-chat-teammate@example.com", exact: true })).toHaveCount(1);
    await expect(sender.getByText("Start a conversation", {exact: true})).toHaveCount(0);
    await sender.getByRole("button", { name: "browser-chat-teammate@example.com", exact: true }).click();
    await expect(sender.getByRole("button", { name: /Conversations/ })).toBeHidden();
    await recipient.getByRole("button", { name: /browser-test@example\.com/ }).last().click();
    const outgoing = sender.getByRole("region", { name: "browser-chat-teammate@example.com", exact: true });
    const incoming = recipient.getByRole("region", { name: /browser-test@example\.com/ });
    await expect(outgoing.getByText("Live", { exact: true })).toBeVisible();
    await expect(incoming.getByText("Live", { exact: true })).toBeVisible();
    const text = "Realtime chat " + Date.now();
    await outgoing.getByRole("textbox", { name: "Write a message" }).fill(text);
    await outgoing.getByLabel("Attach chat files").setInputFiles({
      name: "chat-notes.txt", mimeType: "text/plain", buffer: Buffer.from("Private chat attachment"),
    });
    await outgoing.getByRole("button", { name: "Send message", exact: true }).click();
    await expect(incoming.getByText(text, { exact: true })).toBeVisible({ timeout: 10_000 });
    const avatar = incoming.getByRole("article").filter({hasText: text}).locator(":scope > span").first();
    await expect(avatar).toHaveCSS("width", "30px");
    await expect(avatar).toHaveCSS("height", "30px");
    await expect(recipient.getByRole("button", {name: /Conversations/})).toBeVisible();
    const download = recipient.waitForEvent("download");
    await incoming.getByRole("button", { name: /chat-notes.txt/ }).last().click();
    expect((await download).suggestedFilename()).toBe("chat-notes.txt");
    await expect(incoming.getByRole("button", { name: "Delete", exact: true })).toHaveCount(0);
    await expect.poll(() => recipient.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  } finally {
    await first.close();
    await second.close();
  }
});
