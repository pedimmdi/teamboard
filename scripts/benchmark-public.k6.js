import { check } from "k6";
import exec from "k6/execution";
import http from "k6/http";

function loopbackOrigin(port) {
  if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
    throw new Error("Use a valid local port.");
  }
  return `http://127.0.0.1:${port}`;
}

const frontend = loopbackOrigin(__ENV.E2E_FRONTEND_PORT || "3100");
const api = loopbackOrigin(__ENV.E2E_BACKEND_PORT || "8100");
const pages = ["/", "/fa", "/blog", "/fa/blog"];
const resources = [
  "/api/v1/website/blog/?page=1&page_size=10&lang=en",
  "/api/v1/website/blog/?page=1&page_size=10&lang=fa",
  "/api/v1/website/policy/",
];
const traffic = {
  executor: "constant-arrival-rate",
  timeUnit: "1s",
  duration: "30s",
  preAllocatedVUs: 8,
  maxVUs: 12,
};
const request = { redirects: 0, timeout: "5s" };

export const options = {
  scenarios: {
    public_pages: { ...traffic, rate: 8, exec: "publicPage" },
    public_api: { ...traffic, rate: 5, exec: "publicApi" },
  },
  thresholds: {
    checks: ["rate==1"],
    dropped_iterations: ["count==0"],
    http_req_failed: ["rate<0.01"],
    "http_req_waiting{scenario:public_pages}": ["p(95)<800"],
    "http_req_waiting{scenario:public_api}": ["p(95)<400"],
  },
};

export function setup() {
  for (const page of pages) {
    if (http.get(frontend + page, request).status !== 200) {
      throw new Error(`Frontend fixture did not start at ${frontend + page}.`);
    }
  }
  for (const resource of resources) {
    if (http.get(api + resource, request).status !== 200) {
      throw new Error(`API fixture did not start at ${api + resource}.`);
    }
  }
}

export function publicPage() {
  const page = pages[exec.scenario.iterationInTest % pages.length];
  const response = http.get(frontend + page, { ...request, tags: { name: page } });
  check(response, {
    "public page returns HTML": (value) => value.status === 200 && value.headers["Content-Type"]?.includes("text/html"),
  });
}

export function publicApi() {
  const resource = resources[exec.scenario.iterationInTest % resources.length];
  const response = http.get(api + resource, { ...request, tags: { name: resource } });
  check(response, {
    "public API returns JSON": (value) => value.status === 200 && value.headers["Content-Type"]?.includes("application/json"),
  });
}
