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
  const workspaceCreated = page.waitForResponse((response) =>
    response.request().method() === "POST" &&
    response.url().endsWith("/api/v1/workspaces/") && response.status() === 201);
  await workspaceDialog.getByRole("button", { name: "Create workspace", exact: true }).click();
  const createdWorkspace = await (await workspaceCreated).json();
  await page.goto(`/dashboard/workspaces/${createdWorkspace.slug}/projects`);
  await page.getByRole("button", { name: "New project", exact: true }).click();
  const projectDialog = page.getByRole("dialog", { name: "New project" });
  await projectDialog.getByRole("textbox").first().fill(project);
  await projectDialog.getByRole("button", { name: "Create project" }).click();
  await page.getByRole("link", { name: new RegExp(project) }).filter({ visible: true }).first().click();
  await page.getByRole("button", { name: "New task", exact: true }).filter({ visible: true }).first().click();
  const taskDialog = page.getByRole("dialog", { name: "New task" });
  await taskDialog.getByRole("textbox").first().fill("Browser test task");
  await taskDialog.getByLabel("Due date").fill(new Date().toISOString().slice(0, 10));
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

  await drawer.getByRole("button", { name: "Details", exact: true }).click();
  await drawer.getByLabel("Status", { exact: true }).selectOption("done");
  await drawer.getByRole("button", { name: "Save changes" }).click();
  await drawer.getByRole("button", { name: "Back to tasks" }).click();
  const completedTitle = page.getByRole("button", { name: "Browser test task", exact: true });
  await expect(completedTitle.locator("span")).toHaveCSS("text-decoration-line", "line-through");
  await completedTitle.click();
  await drawer.getByRole("button", { name: "Details", exact: true }).click();
  await drawer.getByLabel("Status", { exact: true }).selectOption("todo");
  await drawer.getByRole("button", { name: "Save changes" }).click();
  await drawer.getByRole("button", { name: "Back to tasks" }).click();
  await expect(page.getByRole("button", { name: "Browser test task", exact: true }).locator("span"))
    .toHaveCSS("text-decoration-line", "none");

  const timeline = /\/calendar\/timeline\/\?/;
  await page.route(timeline, (route) => route.abort());
  await page.getByRole("navigation", { name: "Project navigation" })
    .getByRole("link", { name: "Calendar" }).click();
  const calendar = page.getByRole("region", { name: "Calendar", exact: true });
  const agenda = calendar.getByRole("region", { name: "Day agenda" });
  await expect(calendar.getByRole("alert")).toBeVisible();
  await page.unroute(timeline);
  await calendar.getByRole("button", { name: "Try again" }).click();
  await expect(agenda.getByRole("link", { name: "Browser test task" }))
    .toHaveAttribute("href", /\/tasks\?task=/);
  await calendar.getByLabel("Show").selectOption("event");
  await expect(agenda.getByText("No items for this day.")).toBeVisible();
  await calendar.getByRole("button", { name: "New event" }).click();
  const event = page.getByRole("dialog", { name: "New event" });
  await event.getByLabel("Title").fill("Calendar review");
  await event.getByLabel("Type").selectOption("meeting");
  const starts = await event.getByLabel("Starts at (UTC)").boundingBox();
  const ends = await event.getByLabel("Ends at (UTC)").boundingBox();
  expect(ends.x - (starts.x + starts.width)).toBeGreaterThanOrEqual(8);
  await event.getByLabel("All day").check();
  await event.getByRole("button", { name: "Save event" }).click();
  await expect(agenda.getByRole("button", { name: "Calendar review", exact: true })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("navigation", { name: "Dashboard" })
    .getByRole("link", { name: "Calendar" }).click();
  await calendar.getByRole("button", { name: "New event" }).click();
  const workspaceEvent = page.getByRole("dialog", { name: "New event" });
  await workspaceEvent.getByLabel("Project").selectOption({ label: project });
  await workspaceEvent.getByLabel("Title").fill("Workspace calendar review");
  await workspaceEvent.getByLabel("Ends at (UTC)").fill(
    await workspaceEvent.getByLabel("Starts at (UTC)").inputValue(),
  );
  await workspaceEvent.getByRole("button", { name: "Save event" }).click();
  await expect(workspaceEvent.getByRole("alert")).toContainText("end after the start");
  await workspaceEvent.getByLabel("All day").check();
  await workspaceEvent.getByRole("button", { name: "Save event" }).click();
  await expect(agenda.getByRole("button", { name: "Workspace calendar review" })).toBeVisible();
  await agenda.getByRole("button", { name: "Calendar review", exact: true }).click();
  const readOnlyEvent = page.getByRole("dialog", { name: "Calendar review", exact: true });
  await expect(readOnlyEvent.getByText(/All day/)).toBeVisible();
  await readOnlyEvent.getByRole("link", { name: "Open project calendar" }).click();

  await calendar.getByRole("button", { name: "Next month" }).click();
  await expect(agenda.getByText("No items for this day.")).toBeVisible();
  await calendar.getByRole("button", { name: "Today" }).click();
  await agenda.getByRole("button", { name: "Calendar review", exact: true }).click();
  const edit = page.getByRole("dialog", { name: "Edit event" });
  await edit.getByLabel("Title").fill("Updated calendar review");
  await edit.getByRole("button", { name: "Save event" }).click();
  await agenda.getByRole("button", { name: "Updated calendar review" }).click();
  await edit.getByRole("button", { name: "Delete event" }).click();
  await page.getByRole("dialog", { name: "Delete event?" })
    .getByRole("button", { name: "Delete event" }).click();
  await expect(agenda.getByRole("button", { name: "Updated calendar review" })).toHaveCount(0);
  await expect(agenda.getByRole("link", { name: "Browser test task" })).toBeVisible();
});
