import { expect, test } from "@playwright/test";

test("signed-out visitors are redirected from protected pages and can reach account recovery", async ({ page }) => {
  await page.goto("/dashboard/security");
  await expect(page).toHaveURL(/\/login/);
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await expect(page).toHaveURL(/\/forgot-password/);
  await expect(page.getByRole("textbox", { name: "Email address" })).toBeVisible();
});

test("sign in, create workspace, project and task, then discuss the task", async ({ page }) => {
  test.setTimeout(90_000);
  const suffix = Date.now();
  const workspace = `E2E workspace ${suffix}`;
  const project = `E2E project ${suffix}`;
  await page.goto("/login");
  await page.getByLabel("Email address").fill("browser-test@example.com");
  await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
  await page.goto("/dashboard/workspaces");
  await page.getByRole("button", { name: "Create workspace", exact: true }).click();
  const workspaceDialog = page.getByRole("dialog");
  await workspaceDialog.getByRole("textbox").fill(workspace);
  await workspaceDialog.getByRole("button", { name: "Create workspace", exact: true }).click();
  await page.getByRole("link", { name: new RegExp(workspace) }).click();
  await page.getByRole("button", { name: "New project", exact: true }).click();
  const projectDialog = page.getByRole("dialog", { name: "New project" });
  await projectDialog.getByRole("textbox").first().fill(project);
  await projectDialog.getByRole("button", { name: "Create project" }).click();
  await page.getByRole("link", { name: new RegExp(project) }).filter({ visible: true }).first().click();
  await page.getByRole("button", { name: "New task", exact: true }).filter({ visible: true }).first().click();
  const taskDialog = page.getByRole("dialog", { name: "New task" });
  await taskDialog.getByRole("textbox").first().fill("Browser test task");
  await taskDialog.getByRole("button", { name: "Create task" }).click();
  await page.getByRole("button", { name: "Browser test task", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Task", exact: true });
  await expect(drawer.getByRole("button", { name: "Comments (0)" })).toHaveAttribute("aria-pressed", "true");
  await drawer.getByLabel("Attach file").setInputFiles({
    name: "invalid.exe", mimeType: "application/octet-stream", buffer: Buffer.from("invalid"),
  });
  await drawer.getByRole("button", { name: "Post comment" }).click();
  await expect(drawer.getByRole("alert")).toContainText("Upload a valid");
  await drawer.getByRole("button", { name: "Remove invalid.exe" }).click();
  await drawer.getByRole("textbox", { name: "Write a comment" }).fill("Browser test comment");
  await drawer.getByRole("button", { name: "Post comment" }).click();
  await expect(drawer.getByText("Browser test comment", { exact: true })).toBeVisible();
  await drawer.getByRole("button", { name: "Reply", exact: true }).click();
  await drawer.getByRole("textbox", { name: "Write a comment" }).fill("Browser test reply");
  await drawer.getByRole("button", { name: "Post comment" }).click();
  await expect(drawer.getByText("Browser test reply", { exact: true })).toBeVisible();
  const parent = drawer.getByRole("article").filter({ hasText: "Browser test comment" });
  await drawer.getByRole("button", { name: /^Reply to / }).click();
  await expect(parent).toBeInViewport();
  await expect(parent).not.toBeFocused();
  await parent.getByRole("button", { name: /Comment actions for/ }).click();
  await drawer.getByRole("button", { name: "Delete comment", exact: true }).click();
  await page.getByRole("dialog", { name: "Delete this comment?" }).getByRole("button", { name: "Delete comment", exact: true }).click();
  await expect(drawer.getByRole("button", { name: "Comments (1)" })).toBeVisible();
  await expect(drawer.getByText("Browser test comment", { exact: true })).toHaveCount(0);
  await expect(drawer.getByText("Browser test reply", { exact: true })).toBeVisible();
});
