import { expect, test } from "@playwright/test";

async function signIn(page) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("browser-reminder@example.com");
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("My tasks today", { exact: true })).toBeVisible();
}

test("unmatched URLs return HTTP 404 with a localized home link", async ({ page }) => {
  const response = await page.goto("/fa/route-that-does-not-exist");
  expect(response.status()).toBe(404);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  const heading = page.getByRole("heading", { name: "۴۰۴ — صفحه پیدا نشد" });
  await expect(heading).toBeFocused();
  await page.keyboard.press("Tab");
  const home = page.getByRole("link", { name: "رفتن به خانه" });
  await expect(home).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/fa$/);
});

test("a stalled session request leaves loading, keeps its URL, and recovers on retry", async ({ page }) => {
  await signIn(page);
  let release;
  const stall = new Promise((resolve) => { release = resolve; });
  const refresh = "**/api/v1/accounts/refresh/";
  const clientRequest = page.waitForRequest(refresh);
  await page.route(refresh, async (route) => {
    await stall;
    await route.abort().catch(() => {});
  }, { times: 1 });

  try {
    await page.goto("/dashboard");
    await clientRequest;
    await expect(page.getByRole("status").filter({ hasText: "Checking your session…" })).toBeVisible();
    const heading = page.getByRole("heading", { name: "Couldn’t check your session" });
    await expect(heading).toBeFocused({ timeout: 15_000 });
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Try again" })).toBeFocused();
    release();
    await page.keyboard.press("Enter");
    await expect(page.getByText("My tasks today", { exact: true })).toBeVisible();
  } finally {
    release();
  }
});

test("dashboard shows API and runtime recovery and both retry actions reopen the content", async ({ page }) => {
  await signIn(page);
  const dataRoute = "**/api/v1/workspaces/dashempty/dashboard/";
  const target = "/dashboard/workspaces/dashempty/dashboard";
  await page.route(dataRoute, (route) => route.abort(), { times: 1 });
  await page.goto(target);
  const alert = page.getByRole("alert").filter({ hasText: "Unable to load this workspace’s dashboard." });
  await expect(alert).toBeVisible();
  await alert.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("My tasks today", { exact: true })).toBeVisible();

  await page.route(dataRoute, (route) => route.fulfill({ json: {} }), { times: 1 });
  await page.goto(target);
  const fallback = page.getByRole("heading", { name: "This page couldn’t be displayed" });
  await expect(fallback).toBeFocused();
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("My tasks today", { exact: true })).toBeVisible();
});

test("dashboard offers a retry and workspace list when initial workspace selection fails", async ({ page }) => {
  await signIn(page);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  const lookup = /\/api\/v1\/workspaces\/\?page=1$/;
  await page.route(lookup, (route) => route.abort(), { times: 1 });
  await page.goto("/dashboard");
  const heading = page.getByRole("heading", { name: "Unable to select your workspace" });
  await expect(heading).toBeFocused();
  await expect(page.getByRole("link", { name: "View workspaces" })).toHaveAttribute("href", "/dashboard/workspaces");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("My tasks today", { exact: true })).toBeVisible({ timeout: 15_000 });
});
