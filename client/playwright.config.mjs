import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  retries: 0,
  use: { baseURL: "http://localhost:3100", trace: "retain-on-failure" },
  projects: [{
    name: "chromium",
    use: { ...devices["Desktop Chrome"], channel: process.env.E2E_BROWSER_CHANNEL },
  }],
  webServer: [{
    command: process.env.E2E_PYTHON
      ? `"${process.env.E2E_PYTHON}" browser_test_server.py`
      : "python browser_test_server.py",
    cwd: "../config",
    url: "http://127.0.0.1:8100/api/schema/",
    timeout: 120_000,
  }, {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
    env: { NEXT_PUBLIC_API_URL: "http://localhost:8100" },
    url: "http://localhost:3100/login",
    reuseExistingServer: false,
    timeout: 120_000,
  }],
});
