# TeamBoard MCP

TeamBoard exposes an opt-in Streamable HTTP endpoint at `/mcp`. An OAuth connection acts as the user who approved it. The existing backend enforces current workspace, project, task and conversation access. The default Django application continues to serve the existing web product and REST API.

## Run locally

Use a disposable PostgreSQL database and Redis. Start with the environment described in the [README](../README.md#start-locally). The two browser origins must use the same hostname, with explicit ports. The commands here use PowerShell from the repository root:

```powershell
python -m pip install -r requirements-mcp.txt
$env:FRONTEND_URL = 'http://localhost:3100'
$env:TEAMBOARD_MCP_LOCAL_ISSUER = 'http://localhost:8118'
Set-Location config
python manage.py migrate --settings=config.mcp_local_settings
python manage.py create_local_mcp_client --settings=config.mcp_local_settings --name 'Local MCP client' --redirect-uri 'http://127.0.0.1:6274/callback'
python -m uvicorn config.mcp_local_asgi:application --host 127.0.0.1 --port 8118 --lifespan on --no-proxy-headers --no-access-log
```

Register the exact callback supplied by your local OAuth client. The command prints its public client ID. Use OAuth authorization code with PKCE `S256`, token endpoint authentication method `none`, scope `teamboard.read` and resource `http://localhost:8118/mcp`. Replace the example callback with your client's callback and port.

In a second terminal, from `client/`:

```powershell
$env:TEAMBOARD_MCP_LOCAL_UI = '1'
$env:NEXT_PUBLIC_API_URL = 'http://localhost:8118'
npm run dev -- --port 3100
```

Discovery lives at `/.well-known/oauth-authorization-server` and `/.well-known/oauth-protected-resource/mcp` on the issuer. The `/oauth/authorize/` endpoint validates the OAuth request before opening TeamBoard's first-party consent UI. The authorized client exchanges its code at `/oauth/token/` and can revoke at `/oauth/revoke/`. The local runner uses preregistered loopback clients. The public guides are at `/mcp` and `/fa/mcp`. Signed-in users manage their connections under **Security → AI connections**.

| Tool | Result |
| --- | --- |
| `teamboard_whoami` | Current account ID, email and profile names. |
| `teamboard_list_workspaces` | Current memberships with a bounded page and next-page number. |
| `teamboard_get_workspace` | One currently accessible workspace by slug. |
| `teamboard_list_projects` | Accessible projects in a workspace. Search by name and page by most recent creation. |
| `teamboard_get_project` | Exact project ID in a workspace, current effective project role and bounded description. |
| `teamboard_list_tasks` | Tasks in an exact authorized project, or all accessible projects within one workspace. Filter by statuses, priority, assignee, due date, overdue status and search text. |
| `teamboard_get_task` | Exact task with its bounded description and comment count. |
| `teamboard_list_task_comments` | One task's comments and reply relationships, oldest first. Attachment presence is a boolean. |
| `teamboard_get_task_comment` | Exact comment scoped to the workspace, project and task. |
| `teamboard_list_chats` | Existing direct and project conversations the user can access, newest activity first. |
| `teamboard_list_chat_messages` | Recent non-deleted messages with truncated text where needed and attachment presence only. |
| `teamboard_get_chat_unread_count` | Unread message count in accessible workspace conversations. |
| `teamboard_list_notifications` | Accessible inbox events, newest first. Pass `read: false` for unread events. |
| `teamboard_get_notification_unread_count` | Unread notifications in the current user's accessible inbox. |

Other read tools cover workspace and project rosters and exact-email lookup, workspace invitation status for managers, the signed-in user's web session summary, calendar and timeline, private reminders, dashboard and workload, historical report comparisons, published blog content in both languages, and attachment metadata. `tools/list` returns the input and result schemas for every available tool. A private file opens through TeamBoard's existing authorized download flow.

List calls accept up to 20 rows per page and return `next_page` when another supported page is available. Use exact workspace slugs and resource IDs from the results. Dates are Gregorian `YYYY-MM-DD`. For example, `teamboard_list_tasks` with the workspace slug, `assignee_id: "me"` and `overdue: true` answers “Show my overdue tasks in this workspace” and «تسک‌های عقب‌افتادهٔ من در این فضای کاری را نمایش بده». `due_before` is exclusive. TeamBoard uses the current UTC date for the overdue filter. Projects, tasks, comments, chats and inbox entries retain their existing access rules. Text from those records is user content. Attachment downloads and invitation credentials stay in TeamBoard's authorized web flows.

### Write and sensitive scopes

- `teamboard.read` is the base scope. Add `teamboard.write` to create or edit workspace and project metadata, create, edit and move tasks, post and edit comments, start direct chats and send messages, mark notifications as read, and manage calendar events and your own task reminders.
- Add `teamboard.sensitive` with both other scopes to request task deletion. Open the returned review link in TeamBoard and confirm or deny the exact task as the authorizing user. Approval expires after ten minutes and rechecks current project management access and the task version before deletion. Workspace ownership, role changes, invitation sends, and additional destructive actions use the existing web interface.
- Generate a UUID `idempotency_key` for each new operation. Preserve the same key and inputs when retrying. Receipts last 24 hours and are committed with the mutation in PostgreSQL. Key reuse with changed input returns a conflict. Retry responses are subject to live permissions.
- Calendar timestamps use ISO 8601 with `Z` or an offset. Use `Asia/Tehran` for a relative reminder in Tehran, plus the local time, such as `09:00`. Convert Persian calendar dates before passing them to tools that require Gregorian dates.

The access token lasts five minutes and the refresh window is eight hours after the paired access token expires. The consent record lasts ten minutes, is bound to an HTTP-only browser cookie, and is consumed after a decision. Token lookup uses a digest and verifies resource, scope, expiration, registered application and live account state. User-side revocation serializes with code exchange, refresh and mutations. A Redis failure stops a rate-limited MCP operation with a temporary-unavailable response. Responses omit bearer tokens, storage keys and invitation credentials.

## Configure the HTTPS profile in a hosted environment

Use `DJANGO_SETTINGS_MODULE=config.mcp_settings` with the same ASGI application when an official HTTPS endpoint is available. This selects the application profile. TLS, trusted forwarding, infrastructure and the official deployment are managed separately.

| Setting | Value |
| --- | --- |
| `TEAMBOARD_MCP_ISSUER` | The canonical HTTPS API origin, with no trailing slash or path. The resource URL is the issuer plus `/mcp`. |
| `FRONTEND_URL` | The HTTPS TeamBoard frontend origin. Use an API and frontend under the same site for first-party consent cookies. |
| `TEAMBOARD_MCP_ALLOWED_CALLBACKS` | JSON object mapping exact approved HTTPS OAuth callback URLs to operator-controlled client names. Dynamic registration is advertised once callbacks are configured. |
| `TEAMBOARD_MCP_UI` | Set to `1` in the Next.js server environment to enable first-party consent, approvals and connection management. |
| `TEAMBOARD_MCP_PUBLIC_URL` | Set in Next.js after the official HTTPS endpoint is online. The public guide then exposes the URL and copy control. |

The HTTPS profile accepts public clients and `client_secret_post` confidential clients. Registration validates exact operator-approved callbacks and ignores caller-supplied branding and URLs. It makes no outbound metadata request. Authorization always requires a resource-bound code and `S256`. Check each platform's exact callback and account requirements before enabling it. [Platform connection guides](mcp-clients.md)

## Verify the local integration

From `config/`, with the disposable PostgreSQL configuration loaded:

```powershell
python manage.py check --settings=config.mcp_local_settings
python manage.py makemigrations --check --dry-run --settings=config.mcp_local_settings
python -m pytest -q ai_integrations/tests --ds=config.mcp_local_settings
python -m pytest -q --ds=config.settings
```

From `client/`, with `POSTGRES_DB=teamboard_e2e`, `E2E_PASSWORD`, Redis and Chromium available:

```powershell
npm run lint
npm run typecheck
npm run test:coverage
npx playwright test --config playwright.mcp.config.mjs
npm run test:e2e
```

The MCP browser fixture starts the actual Uvicorn backend and a built Next.js frontend on dedicated local ports. It exercises sign-in, approval and exchange in English, then denial in Persian dark mode at a mobile viewport. Optional test ports are `E2E_MCP_FRONTEND_PORT` and `E2E_MCP_BACKEND_PORT`.

To run the optional pinned Inspector smoke check, set `E2E_MCP_INSPECTOR=1` and run `npm exec -- playwright test --config playwright.mcp.config.mjs`. The fixture exercises `tools/list` and `teamboard_whoami` over real HTTP using the short-lived browser test credential. If you install Inspector 2.5.0 separately, point `E2E_MCP_INSPECTOR_ENTRY` at its `mcp-inspector` JavaScript entry. See the [Inspector CLI reference](https://github.com/modelcontextprotocol/inspector/tree/main/clients/cli).

Entry points are [ASGI](../config/config/mcp_local_asgi.py), [OAuth and consent](../config/ai_integrations/oauth.py), [read tools](../config/ai_integrations/tools.py), [write tools](../config/ai_integrations/write_tools.py), and [bilingual consent](../client/src/app/(auth)/ai/authorize/page.tsx). The [design notes](mcp-design.md) record the architecture, risk controls and outstanding live tests.
