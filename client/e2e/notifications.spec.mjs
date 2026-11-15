import { expect, test } from "@playwright/test";

test("mobile inbox retries, paginates, filters and updates unread badges", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 844 });
  const countEndpoint = "**/api/v1/notifications/unread-count/";
  await page.route(countEndpoint, (route) => route.abort());
  await page.goto("/login");
  // Confirm the server-rendered sign-in form has hydrated before filling it.
  await expect(async () => {
    await page.getByRole("button", { name: "Show password" }).click();
    await expect(page.getByRole("button", { name: "Hide password" })).toBeVisible({ timeout: 500 });
  }).toPass({ timeout: 15_000 });
  await page.getByRole("button", { name: "Hide password" }).click();
  await page.getByLabel("Email address").fill("browser-test@example.com");
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
  const bell = page.getByRole("banner").getByRole("link", { name: "Notifications", exact: true });
  await expect(bell).toBeVisible();

  const firstPage = /\/api\/v1\/notifications\/\?page=1&page_size=20$/;
  await page.route(firstPage, (route) => route.abort());
  await bell.click();
  await expect(page.getByRole("heading", { name: "Unable to load notifications" })).toBeVisible();
  const retryCount = page.getByRole("button", { name: "Retry unread count" });
  await expect(retryCount).toBeVisible();
  await page.unroute(countEndpoint);
  await retryCount.click();
  await expect(page.getByRole("banner").getByRole("link", { name: "Notifications, 21 unread" })).toBeVisible();
  await page.unroute(firstPage);
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("Showing 1–20 of 21")).toBeVisible();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.getByText("Showing 21–21 of 21")).toBeVisible();

  await page.getByRole("button", { name: /^Mark as read:/ }).click();
  await expect(page.getByRole("banner").getByRole("link", { name: "Notifications, 20 unread" })).toBeVisible();

  await page.getByRole("button", { name: "Read", exact: true }).click();
  await expect(page.getByText("Showing 1–1 of 1")).toBeVisible();
  await expect(page.getByRole("link", { name: "Your workspace role was updated" })).toHaveAttribute(
    "href", /\/dashboard\/workspaces\/[^/]+\/members$/,
  );

  await page.getByRole("button", { name: "Unread", exact: true }).click();
  await expect(page.getByText("Showing 1–20 of 20")).toBeVisible();
  await page.getByRole("button", { name: "Mark all as read" }).click();
  await expect(page.getByRole("heading", { name: "No unread notifications" })).toBeVisible();
  await expect(page.getByRole("banner").getByRole("link", { name: "Notifications", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 900 });
  const desktopInbox = page.getByRole("navigation", { name: "Workspace" })
    .getByRole("link", { name: "Notifications", exact: true });
  await expect(desktopInbox).toHaveAttribute("aria-current", "page");
  await page.getByRole("button", { name: "All", exact: true }).click();
  await expect(page.getByText("Showing 1–20 of 21")).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark all as read" })).toBeDisabled();
});
