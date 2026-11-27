import { execFile } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";
import { expect, test } from "@playwright/test";

const api = `http://localhost:${process.env.E2E_MCP_BACKEND_PORT || "8118"}`;
const email = "mcp-browser@example.invalid";
const exec = promisify(execFile);

async function inspectWithMcpInspector(token, outputPath) {
  await mkdir(outputPath, { recursive: true });
  const entry = process.env.E2E_MCP_INSPECTOR_ENTRY;
  const launcher = entry ? [entry] : [
    process.env.npm_execpath, "exec", "--yes", "--package=@modelcontextprotocol/inspector@2.5.0", "--", "mcp-inspector",
  ];
  for (const [method, extra, expected] of [
    ["tools/list", [], "teamboard_request_task_deletion"],
    ["tools/call", ["--tool-name", "teamboard_whoami"], email],
  ]) {
    try {
      const { stdout } = await exec(process.execPath, [
        ...launcher, "--cli", "--server-url", `${api}/mcp`, "--transport", "http",
        "--protocol-era", "legacy", "--method", method, ...extra, "--header", `Authorization: Bearer ${token}`,
      ], { env: { ...process.env, MCP_CATALOG_PATH: join(outputPath, "inspector.json") }, timeout: 45_000 });
      expect(stdout.includes(expected)).toBe(true);
    } catch (error) {
      const diagnostics = String(error.stderr || "").split(token).join("[test token omitted]").slice(-1000);
      const reason = error.killed ? "timed out" : `failed (${error.code ?? "invalid output"})`;
      throw new Error(`MCP Inspector ${method} ${reason}. ${diagnostics}`);
    }
  }
}

for (const locale of ["en", "fa"]) {
  test(`local MCP consent uses real TeamBoard login in ${locale}`, async ({ page, request, baseURL }, testInfo) => {
    if (process.env.E2E_MCP_INSPECTOR === "1") test.setTimeout(120_000);
    const persian = locale === "fa";
    if (persian) await page.setViewportSize({ width: 390, height: 844 });
    await page.context().addCookies([
      { name: "teamboard-locale", value: locale, url: baseURL },
      { name: "teamboard-theme", value: persian ? "dark" : "light", url: baseURL },
    ]);
    const callback = `${baseURL}/mcp-test-callback`;
    await page.route((url) => `${url.origin}${url.pathname}` === callback, (route) =>
      route.fulfill({ contentType: "text/plain", body: "Local OAuth callback" }));

    const verifier = randomBytes(48).toString("base64url");
    const state = randomBytes(16).toString("base64url");
    const params = new URLSearchParams({
      client_id: "teamboard-local-browser-test",
      redirect_uri: callback,
      response_type: "code",
      scope: persian ? "teamboard.read" : "teamboard.read teamboard.write",
      state,
      resource: `${api}/mcp`,
      code_challenge: createHash("sha256").update(verifier).digest("base64url"),
      code_challenge_method: "S256",
    });

    await page.goto(`${api}/oauth/authorize/?${params}`);
    await page.getByRole("link", { name: persian ? "ورود برای بررسی درخواست" : "Sign in to review" }).click();
    await page.getByLabel(persian ? "نشانی ایمیل" : "Email address", { exact: true }).fill(email);
    await page.getByLabel(persian ? "گذرواژه" : "Password", { exact: true }).fill(process.env.E2E_PASSWORD);
    await page.getByRole("button", { name: persian ? "ورود" : "Sign in", exact: true }).click();
    await expect(page.getByText("Browser fixture", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(email, { exact: true })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("dir", persian ? "rtl" : "ltr");
    await expect(page.locator("html")).toHaveAttribute("data-theme", persian ? "dark" : "light");

    const callbackNavigation = page.waitForURL((url) => `${url.origin}${url.pathname}` === callback);
    await page.getByRole("button", { name: persian ? "رد درخواست" : "Allow read and write access", exact: true }).click();
    await callbackNavigation;
    const outcome = new URL(page.url()).searchParams;
    expect(outcome.get("state")).toBe(state);
    expect(outcome.get("iss")).toBe(api);
    if (persian) {
      expect(outcome.get("error")).toBe("access_denied");
      expect(outcome.get("code")).toBeNull();
      return;
    }
    const exchange = await request.post(`${api}/oauth/token/`, { form: {
      client_id: "teamboard-local-browser-test", code: outcome.get("code"),
      grant_type: "authorization_code", code_verifier: verifier,
      redirect_uri: callback, resource: `${api}/mcp`,
    }});
    expect(exchange.status()).toBe(200);
    const token = await exchange.json();
    expect(token.scope.split(" ").sort()).toEqual(["teamboard.read", "teamboard.write"]);
    const result = await request.post(`${api}/mcp`, {
      headers: {
        Authorization: `Bearer ${token.access_token}`,
        Accept: "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-11-25",
      },
      data: { jsonrpc: "2.0", method: "tools/call", id: 1, params: { name: "teamboard_whoami", arguments: {} } },
    });
    expect(result.status()).toBe(200);
    expect((await result.json()).result.structuredContent.email).toBe(email);
    if (process.env.E2E_MCP_INSPECTOR === "1") await inspectWithMcpInspector(token.access_token, testInfo.outputDir);

    await page.goto("/dashboard/security/ai");
    await expect(page.getByRole("heading", { name: "AI connections", exact: true })).toBeVisible();
    await expect(page.getByText("Read and write access", { exact: true })).toBeVisible();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Revoke Browser fixture", exact: true }).click();
    await expect(page.getByText("You have no active AI connections.")).toBeVisible();
    const revoked = await request.post(`${api}/mcp`, {
      headers: { Authorization: `Bearer ${token.access_token}`, Accept: "application/json, text/event-stream" },
      data: { jsonrpc: "2.0", method: "tools/list", id: 2 },
    });
    expect(revoked.status()).toBe(401);
  });
}
