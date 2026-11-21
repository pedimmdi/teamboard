# TeamBoard

TeamBoard is a workspace for planning projects, tracking tasks on a Kanban board, and discussing work in context. It pairs a Next.js frontend with a Django REST API and PostgreSQL.

## Features

- **Workspace Dashboard** is the signed-in landing page, with nine private workspace-scoped summaries, count/list views and up to five preview items. Switch workspaces to change the overview; the last valid workspace is restored on return. Account details now live at `/dashboard/profile`. Mobile navigation places Dashboard between Calendar and Chats.

- **Accounts** with email verification, password reset, profile images, and session management.
- **Workspaces** with invitations, ownership transfer, member management, and workspace images. Owner, Admin, and Member badges use green, purple, and blue respectively.
- **Projects** with membership, project images, and Board and List views. Board is the default and the browser remembers the selected view.
- **Tasks** with four Kanban columns, drag-and-drop, assignees, priorities, due dates, and filters. Open a card to see its discussion and details.
- **Private task reminders** with up to three active reminders per user/task, fixed times or due-date presets, IANA timezones, and automatic rescheduling. Reminders arrive in the existing notification inbox; manage them from the task drawer on desktop or mobile.
- **Comments** with replies, project-member mentions, editing, moderation, attachment downloads, and counts on task cards.
- **Notifications** with an account-wide inbox, unread badge, read filters and links to the related project or task. Workspace invitations are accepted using their email link.
- **Calendars** with month, week, and day views for workspaces and projects, a day agenda for events and task due dates, and project event management. Calendar dates and event entry use UTC. The agenda can display timed events in the browser’s local timezone. The timeline includes events and full-day task due dates that overlap the requested range. The range end is exclusive.

- **Reports** for projects and workspaces with current task statistics, historical activity, date and task filters, workload, paginated project comparisons, and CSV export.

- **Chats** with project conversations and direct workspace messages, replies, editing, deletion and private TXT/JPEG/PNG attachments. Live updates reconnect automatically, with periodic REST synchronization when needed.

## Stack and layout

| Path | Purpose |
| --- | --- |
| `client/` | Next.js App Router, React, TypeScript, and frontend tests |
| `config/` | Django configuration, REST apps, database migrations, and backend tests |
| `config/schema.yml` | Checked-in OpenAPI schema |
| `docker/` and `docker-compose.yml` | Local PostgreSQL, API, and frontend services |
| `.github/workflows/tests.yml` | Backend and frontend checks in GitHub Actions |

## Local setup

Install Docker with Compose v2. Clone the repository and copy `.env.example` to `.env`. In PowerShell, use `Copy-Item .env.example .env`. Set local values for `SECRET_KEY` and `POSTGRES_PASSWORD` before starting a new stack.

```sh
git clone https://github.com/pedimmdi/teamboard.git
cd teamboard
docker compose up -d --build
docker compose ps
```

The Compose backend applies pending migrations before starting Django. Follow startup or migration output with `docker compose logs -f backend`.

| Service | Address |
| --- | --- |
| TeamBoard | http://localhost:3000 |
| Django admin | http://localhost:8000/admin/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| OpenAPI schema | http://localhost:8000/api/schema/ |

Register in the web app and use the verification link from the backend logs when using the default console email backend. To create a separate Django administrator, run `docker compose exec backend python manage.py createsuperuser`.

### Updating an existing checkout

After pulling changes, run `docker compose up -d --build`. If the backend container was already running and Compose leaves it in place, restart it with `docker compose restart backend` to apply migrations before serving requests. You can also apply migrations directly:

```sh
docker compose exec backend python manage.py migrate --noinput
docker compose exec backend python manage.py migrate --check
```

If the Comments tab repeatedly reports a generic error, check the backend logs and confirm that `comments.0003_private_attachment_storage` is marked applied. Retry the tab after the backend is ready.

Django's development auto-reload picks up mounted Python files while the backend is running. Run the migration command after pulling changes to the schema. If Projects opens but the Tasks board returns a 500 and the backend log mentions `tasks_task.completed_at`, check that `tasks.0006_track_task_status` is applied with `docker compose exec backend python manage.py showmigrations tasks`.

### Running the frontend outside Docker

Keep the database and backend running. Stop the Compose frontend with `docker compose stop frontend`. Then run:

```sh
cd client
npm ci
npm run dev
```

The default API address is `http://localhost:8000`. Set `NEXT_PUBLIC_API_URL` before building if using another address. Match `FRONTEND_URL` to the frontend origin for local API requests and account links.

## Permissions and API

API routes are under `/api/v1/`. The frontend uses bearer access tokens and a refresh cookie. See the OpenAPI schema for request fields and response codes.

| Resource | Base path relative to `/api/v1/` |
| --- | --- |
| Accounts and sessions | `accounts/` |
| Workspaces | `workspaces/` |
| Members and invitations | `workspaces/<slug>/members/`, `workspaces/<slug>/invitations/` |
| Projects | `workspaces/<slug>/projects/` |
| Tasks | `workspaces/<slug>/projects/<project_id>/tasks/` |
| Task comments | `workspaces/<slug>/projects/<project_id>/tasks/<task_id>/comments/` |
| Private task reminders | `workspaces/<slug>/projects/<project_id>/tasks/<task_id>/reminders/` |

Workspace Owners and Admins can manage project access across the workspace. Project Managers can manage the projects they belong to. Project Members can work on tasks and participate in discussions within projects they can access.

A comment request accepts `body` and optional `reply_to`. Send multipart form data to include one `attachment`. Use `@` in the composer to select a project member. Authors can edit their own comments. Managers and workspace administrators can moderate comments. Download an attachment through the authenticated `<comment_id>/attachment/` endpoint.

Task reminders use PostgreSQL as their scheduling ledger, with the existing Celery worker and Beat checking every 60 seconds. Each user manages only their own reminders, subject to live task access. Due dates have no deadline hour: relative reminders default to 09:00 in the selected timezone. Delivery resumes after service outages without creating duplicate notifications. See [reminder API, scheduling and recovery](docs/task-reminders.md) for states, DST rules, limits and operational checks.

### Advanced Reports API

The existing project and workspace overview endpoints return current statistics. Under either reports URL, use:

- `history/` for UTC daily or Monday-based weekly creation and completion counts, and an equally long preceding period. Use `period=7d|30d|90d` (default 30 days) or inclusive `start_date` and `end_date`. A completion is a transition into Done, including creation directly in Done. A reopened and later completed task counts again. Historical status, priority, and assignee filters use the snapshot at the transition. Creation of surviving pre-migration tasks uses its recorded creation date and current fields. Completion data before `completion_tracking_since` is unavailable.
- `workload/` for current per-assignee totals, active and completed tasks, overdue tasks, tasks due in the next seven days (including today and day seven), and completion rates. Every task has an assignee.
- `export/` for the current filtered task snapshot as CSV, capped at 5,000 rows.
- Workspace `projects/` for paginated project comparisons. Use `ordering` with `name`, `total_tasks`, `completed_tasks`, or `overdue_tasks` and an optional minus prefix.

Each endpoint accepts `assignee` (user ID or `me`), `status`, and `priority`. Outside historical analytics, date filters apply to task creation. Supply both dates together and use a maximum range of 366 days. Reports and exports include only accessible projects.

## Persistent data and deployment

- Back up PostgreSQL, uploaded avatars, and the private attachment directory together. Docker Compose persists PostgreSQL in `postgres_data`. The backend bind mount persists local uploads in `config/media/` and `config/private_attachments/`.
- Set `COMMENT_ATTACHMENT_ROOT` to a writable absolute path on persistent storage shared by backend replicas. Keep it outside publicly served media. New attachments accept PNG, JPEG, and UTF‑8 text up to 5 MB.
- Before upgrading an existing deployment, pause comment writes and apply migrations with access to both PostgreSQL and the private attachment directory. Migration `comments.0003` copies existing attachments to private storage and removes their binary database column.
- Schedule periodic inspection with `python manage.py cleanup_comment_attachments`. It reports unreferenced files older than 24 hours. During a maintenance window with comment writes and migrations paused, pass `--apply` to remove them. This also retries file deletions that failed after the database commit. Run the command against the database that owns the configured attachment directory.
- Configure production secrets, allowed hosts, HTTPS cookies, and a real email backend. The Compose stack uses Django's development server. Use a production application server for deployment.
- For databases carried over from the old Organizations app, preserve migration history and back up the database before applying workspace migrations.

## Verification

Run the same checks locally that GitHub Actions runs on pushes and pull requests.

```sh
docker compose exec -T backend python manage.py check
docker compose exec -T backend python manage.py makemigrations --check --dry-run
docker compose exec -T backend python manage.py spectacular --validate --fail-on-warn --file /tmp/schema.yml
docker compose exec -T backend python -m pytest -q
```

```sh
cd client
npm ci
npm run lint
npm test
npm run build
```

When changing the API contract, regenerate the checked-in schema with `docker compose exec -T backend python manage.py spectacular --validate --fail-on-warn --file schema.yml`.

### Browser tests

Create an isolated PostgreSQL database named `teamboard_e2e` and set `POSTGRES_DB=teamboard_e2e` and `E2E_PASSWORD` in the test process environment. Use the matching PostgreSQL credentials and a Django environment with the project dependencies installed. Set `E2E_PYTHON` to the virtual environment's Python executable if needed. From `client/` run `npx playwright install chromium` and `npm run test:e2e`. Playwright builds and serves the production frontend on port 3100. For an installed Chrome or Edge, set `E2E_BROWSER_CHANNEL` to `chrome` or `msedge`.

Playwright starts Next.js on port 3100 and Django on port 8100. The test server applies migrations and seeds a verified user in the isolated database. The tests exercise the browser, API and PostgreSQL together. GitHub Actions runs the Chromium suite and saves failure traces.

## License

TeamBoard is distributed under the [MIT License](LICENSE).

Weekly report buckets follow calendar weeks starting on Monday. Their `date` labels that Monday, while `start_date` and `end_date` identify the included portion of each bucket. Boundary weeks can be partial in both the selected and comparison periods.

When updating a running Docker frontend, run `docker compose exec frontend npm ci` and `docker compose restart frontend` to synchronize the persistent dependency volume with the checked-in lockfile.

If Windows reserves port 8000, set `BACKEND_PORT=8001` in `.env` and set any explicit `NEXT_PUBLIC_API_URL` to `http://localhost:8001`. Run `docker compose up -d --force-recreate backend frontend`.

Report CSV downloads start with a UTF-8 BOM and an Excel `sep=,` directive so Persian text and comma-separated columns open correctly regardless of the system list separator. General CSV parsers should skip the directive line.

### Task assignment invariant

Every current task belongs to an active project member. Task creation through the API requires a non-null `assignee`; PATCH may omit this field but cannot clear it. Task and Reports filters no longer offer `unassigned` (legacy task query parameters are rejected).

Migration `tasks.0007` assigns existing unassigned tasks to the eligible project manager with the lowest user ID. Removing a project/workspace member transfers their tasks to the lowest-ID remaining eligible manager in the same transaction. Without a remaining manager, removal is rejected. Direct ORM/bulk inserts without an assignee use the same manager fallback; database checks prevent any task from remaining unassigned. Historical status snapshots are preserved, including genuine null assignments recorded before this rule. The legacy Reports `unassigned_tasks` response field remains for API compatibility and is zero for current tasks.

Workspace information is available at the top of Settings. Chats lists project conversations and a single Direct messages section; the conversation back button is reserved for mobile.

### Chat replies and unread messages

Reply references are UUIDs. `GET /api/v1/workspaces/{slug}/chats/{conversation}/messages/{message}/` retrieves an authorized older message directly; selecting a reply scrolls to its source and highlights it for one second.

`GET /api/v1/workspaces/{slug}/chats/unread/` returns the active workspace total and per-conversation unread counts. Only received, non-deleted messages in accessible project chats or the user's own direct conversations count. Workspace owners/admins can access project chats; ordinary members see only joined projects. `POST .../chats/{conversation}/read/` accepts `message_id` and advances a persistent `(created_at, UUID)` cursor without moving it backwards. It does not mark newer messages as read. The cursor survives deletion of its referenced message and is shared across devices. Migration `chats.0006` preserves existing read pointers.

The navigation and conversation list display 1–10, then `+10`. Counts refresh every 15 seconds while visible, on focus, and after live events or read acknowledgements in the open chat. Errors retain the last known counts and offer retry. Mobile navigation has Projects, Calendar, Chats, and Account; People remains in desktop navigation and workspace tabs.

### Redis and worker infrastructure

Compose runs Redis 7.4 with AOF persistence and `noeviction`, plus a dedicated Celery worker. Channels uses Redis DB 0 for cross-process event delivery; shared Django throttling uses DB 1 with a versioned key prefix; the Celery broker uses DB 2. These logical databases share memory and availability: for larger production deployments use separate managed Redis instances, memory limits, monitoring, authentication/TLS (`rediss://`), backups, and tested recovery. The local Redis port is bound only to loopback; never publish it publicly. Production must set independent environment-prefixed cache keys when sharing a cache instance.

Only unit tests override Redis with isolated in-memory backends. Application startup does not silently switch to in-memory transport on a Redis outage. DRF throttles keep their existing approximate concurrency semantics; they now share counters between processes. They are not a strict distributed quota or a replacement for upstream abuse protection. Redis cache connection errors remain visible rather than silently bypassing throttles.

`RUN_REDIS_TESTS=1 python -m pytest test_infrastructure.py` verifies real cross-process Channels and cache delivery without flushing a shared Redis database. All test keys/groups have unique prefixes and expiry. No JWT, session, membership, permission, message, task, or API response is cached by this change.

### Durable background work

Accounts verification/reset/resend and Workspace invitations now create PostgreSQL outbox jobs; Celery workers deliver email after commit. Chat and Comment attachment deletion also use durable, retryable jobs. A single Beat recovers pending work. Existing orphan cleanup remains conservative and available for maintenance. No tasks, notifications, permissions, memberships, JWTs, sessions or chat messages were moved into a cache.

Read the [infrastructure deployment and recovery guide](docs/infrastructure.md) for worker/Beat commands, SMTP limitations, payload retention, non-root production overlay, shared storage, failure recovery and benchmark results. The 10000-task uncached benchmark does not justify application response caching; only shared throttle history currently uses Django's Redis cache.
