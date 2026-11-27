import { defineConfig, devices } from "@playwright/test";

const port = process.env.E2E_MCP_FRONTEND_PORT || "3110";
const apiPort = process.env.E2E_MCP_BACKEND_PORT || "8118";
const frontend = `http://localhost:${port}`;
const api = `http://localhost:${apiPort}`;
const python = process.env.E2E_PYTHON ? `"${process.env.E2E_PYTHON}"` : "python";

export default defineConfig({
  testDir: "./e2e-mcp",
  outputDir: "test-results/mcp",
  workers: 1,
  use: {
    ...devices["Desktop Chrome"],
    channel: process.env.E2E_BROWSER_CHANNEL,
    baseURL: frontend,
    trace: "retain-on-failure",
  },
  webServer: [{
    command: `${python} tests/mcp_browser_server.py`,
    cwd: "../config",
    env: { FRONTEND_URL: frontend, TEAMBOARD_MCP_LOCAL_ISSUER: api },
    url: `${api}/.well-known/oauth-authorization-server`,
    timeout: 120_000,
  }, {
    command: "npm run build && node e2e/start-frontend.mjs",
    env: {
      NEXT_PUBLIC_API_URL: api,
      TEAMBOARD_MCP_LOCAL_UI: "1",
      HOSTNAME: "127.0.0.1",
      PORT: port,
    },
    url: `${frontend}/login`,
    timeout: 120_000,
  }],
});
