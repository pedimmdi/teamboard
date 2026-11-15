import { defineConfig, devices } from "@playwright/test";

const port = process.env.E2E_FRONTEND_PORT || "3100";
const frontendUrl = `http://localhost:${port}`;

export default defineConfig({
  testDir: "./e2e",
  retries: 0,
  use: { baseURL: frontendUrl, trace: "retain-on-failure" },
  projects: [{
    name: "chromium",
    use: { ...devices["Desktop Chrome"], channel: process.env.E2E_BROWSER_CHANNEL },
  }],
  webServer: [{
    command: process.env.E2E_PYTHON
      ? `"${process.env.E2E_PYTHON}" browser_test_server.py`
      : "python browser_test_server.py",
    cwd: "../config",
    env: { FRONTEND_URL: frontendUrl },
    url: "http://127.0.0.1:8100/api/schema/",
    timeout: 120_000,
  }, {
    command: "npm run build && node e2e/start-frontend.mjs",
    env: {
      NEXT_PUBLIC_API_URL: "http://localhost:8100",
      HOSTNAME: "127.0.0.1",
      PORT: port,
    },
    url: `${frontendUrl}/login`,
    reuseExistingServer: false,
    timeout: 120_000,
  }],
});
