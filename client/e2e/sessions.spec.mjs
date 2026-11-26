import { expect, test } from "@playwright/test";

test("session pagination keeps the last loaded page visible and retries a failed request", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await page.getByLabel("Email address").fill("browser-reminder@example.com");
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 15_000 });

  const sessionEndpoint = /\/api\/v1\/accounts\/sessions\/\?page=\d+$/;
  let failNextPage = true;
  await page.route(sessionEndpoint, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const url = new URL(route.request().url());
    const onFirstPage = url.searchParams.get("page") === "1";
    if (!onFirstPage && failNextPage) {
      failNextPage = false;
      return route.abort();
    }

    url.searchParams.set("page", "1");
    const response = await route.fetch({ url: url.href });
    const body = await response.json();
    const current = body.results.find((session) => session.is_current);
    await route.fulfill({
      response,
      json: {
        count: 21,
        previous: onFirstPage ? null : url.href,
        next: onFirstPage ? url.href.replace("page=1", "page=2") : null,
        results: onFirstPage ? [current] : [{
          ...current,
          id: "other-session",
          is_current: false,
          ip_address: "192.0.2.21",
        }],
      },
    });
  });

  await page.goto("/dashboard/sessions");
  const nav = page.getByRole("navigation", { name: "Session pages" });
  const currentDevice = page.getByText("This device", { exact: true });
  await expect(currentDevice).toBeVisible();
  await expect(nav.getByText("Page 1", { exact: true })).toBeVisible();

  await nav.getByRole("button", { name: "Next page" }).click();
  await expect(page.locator("main").getByRole("alert")).toBeVisible();
  await expect(nav.getByText("Page 1", { exact: true })).toBeVisible();
  await expect(currentDevice).toBeVisible();

  await page.getByRole("button", { name: "Reload sessions" }).click();
  await expect(nav.getByText("Page 2", { exact: true })).toBeVisible();
  await expect(page.getByText("192.0.2.21", { exact: true })).toBeVisible();
  await nav.getByRole("button", { name: "Previous page" }).click();
  await expect(nav.getByText("Page 1", { exact: true })).toBeVisible();
  await expect(currentDevice).toBeVisible();
});
