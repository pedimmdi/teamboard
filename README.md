# TeamBoard

TeamBoard is a bilingual project workspace for planning work, tracking tasks, and discussing decisions in context. It uses Next.js and React for the interface, Django REST Framework for the API, PostgreSQL for application data, and Redis and Celery for live updates and background work.

See [architecture and configuration](docs/architecture.md) for the request flow, API conventions and environment variable reference.

## What you can do

- **Browse the public website** in English at `/` or Persian at `/fa`. Both versions include About, Contact, Blog, Privacy and Terms. The header offers **Open dashboard** when you are signed in. Signing out returns you to the home page in your selected language.
- **Manage accounts and workspaces** with email verification, password reset, profile images, active sessions, invitations, member roles and ownership transfers.
- **Plan projects** on a Kanban board or list. Search and filter tasks, assign teammates, track priorities and due dates, comment with mentions and attachments, and set private reminders.
- **Review the workspace dashboard** for today's tasks, overdue work, upcoming deadlines and follow-up. The browser remembers your last accessible workspace.
- **Coordinate with calendars, chats and reports.** Browse month, week and day views, use direct or project conversations with unread counts, and export filtered reports to CSV.
- **Choose English or Persian and light or dark mode.** The first visit uses English light. Persian uses right-to-left layouts and a Saturday-start Solar Hijri calendar. Calendar times can be displayed in UTC, the browser's timezone, or Iran time. Persian defaults to Iran time and shows the Tehran clock. Timed events retain their UTC instant, and due dates and all-day events retain their civil date.

## Start locally

Install Docker with Compose v2. Copy the environment template, set local values for `SECRET_KEY` and `POSTGRES_PASSWORD`, and launch the services.

```sh
git clone https://github.com/pedimmdi/teamboard.git
cd teamboard
cp .env.example .env
docker compose up -d --build
docker compose ps
```

In PowerShell use `Copy-Item .env.example .env`. Compose applies migrations before starting Django. Follow startup with `docker compose logs -f backend`.

| Service | Default address |
| --- | --- |
| TeamBoard | http://localhost:3000 |
| Django admin | http://localhost:8000/admin/ |
| Swagger / ReDoc | http://localhost:8000/api/docs/ or http://localhost:8000/api/redoc/ |
| OpenAPI schema | http://localhost:8000/api/schema/ |

Register through the web app. With the default console email backend, the verification link appears in the backend logs. Create an administrator with `docker compose exec backend python manage.py createsuperuser`.

### Configuration

| Setting | Use |
| --- | --- |
| `SECRET_KEY`, `POSTGRES_*` | Django signing key and database settings. Use separate values for production and tests. |
| `FRONTEND_URL` | Browser-facing frontend origin used for CORS and account links. |
| `NEXT_PUBLIC_API_URL` | Browser-reachable API origin, set before building the frontend. |
| `WEBSITE_API_URL` | Server-reachable API origin for public pages. Compose uses `http://backend:8000`. |
| `NEXT_PUBLIC_SITE_URL` | Public HTTPS origin used for canonical URLs, social previews, robots and sitemap. |
| `REDIS_URL`, `REDIS_CACHE_URL`, `CELERY_BROKER_URL` | Live events, shared throttle counters and background delivery. |

For native frontend development, keep Django and its services running, stop the Compose frontend, then run `npm ci` and `npm run dev` from `client/`. If Windows reserves port 8000, select a free `BACKEND_PORT` and update `NEXT_PUBLIC_API_URL` before recreating the services.

After pulling a release, run `docker compose up -d --build`. Apply any outstanding migrations before serving the new frontend. Check with `docker compose exec backend python manage.py migrate --check`. If Docker still uses an old frontend dependency volume, run `docker compose exec frontend npm ci` and restart that service.

### Persian font

Use the webfont archive covered by your IranSansX license. From the repository root, install its Persian-number WOFF2 family.

```sh
python client/scripts/install-persian-font.py "/path/to/IranSansX(SemiPro).zip"
```

The installer verifies all 11 faces and creates `client/public/fonts/iransansx/faces.css`. Next.js discovers the installed stylesheet automatically. The directory stays outside Git. Include it in the static assets of the licensed deployment, or use the bundled OFL-licensed Vazirmatn. Set `IRANSANSX_WEBFONT=0` to explicitly select Vazirmatn. Older installations with three individual WOFF2 files can still use `IRANSANSX_WEBFONT=1` until they run the installer.

## Public content and privacy

In Django Admin, open **Website → Blog posts**. Use **English content** for the original title, excerpt and Markdown body and **Persian translation** for Persian copy. A Persian title and body make the translation visible on a published article. Give it a Persian excerpt for the blog listing. The translation uses the same slug under `/fa/blog/`. English-only posts retain their English canonical URL and show a localized fallback notice on direct Persian article links.

Public pages render on the server with language alternates, canonical links and structured metadata. Protected pages send crawler exclusion headers. Only credential-free public API reads are reused on the frontend. Lists and policy data live for 60 seconds and article details for 30 seconds, with bounded per-process storage. The sitemap serves a complete fresh snapshot for five minutes, uses the last good snapshot for up to one hour during an outage, and can always serve the static public URLs. The contact form and privacy page read the retention policy from Django; actual cleanup uses the same setting. See [performance measurements](docs/performance.md).

## API and permissions

| Resource | Path under `/api/v1/` |
| --- | --- |
| Accounts and sessions | `accounts/` |
| Workspaces | `workspaces/` |
| Members and invitations | `workspaces/<slug>/members/` and `workspaces/<slug>/invitations/` |
| Projects | `workspaces/<slug>/projects/` |
| Tasks | `workspaces/<slug>/projects/<project_id>/tasks/` |
| Task comments and reminders | `workspaces/<slug>/projects/<project_id>/tasks/<task_id>/comments/` and `reminders/` |
| Public website | `website/blog/`, `website/contact/`, `website/sitemap/` and `website/policy/` |

The frontend authenticates with bearer access tokens and an HTTP-only refresh cookie. Workspace Owners and Admins can manage project access. Project Managers manage their projects. Project Members can work on tasks and discussions they can access.

The dashboard's Home link opens the public site in the selected language. Request `accounts/sessions/?page=1` for a paginated device inventory or `workspaces/<slug>/chats/direct/?page=1` for paginated direct conversations. On these routes, requests without pagination parameters return an array of up to 100 records. `X-Total-Count` gives the total and `Link` points to the next page when available.

Each current task has a project-eligible assignee. Removing a member transfers tasks to an eligible remaining manager in the same transaction. Without a remaining manager, removal is rejected. The historical report field `unassigned_tasks` remains available for compatibility.

Comments accept Markdown-free text with optional `reply_to` and one multipart attachment. A reply navigates to its source and briefly highlights it. Comment and chat attachments use authorization-checked download endpoints. Chat unread pointers advance monotonically and synchronize across sessions. The navbar displays counts up to ten, then `+10`.

Reports support UTC daily and Monday-start weekly buckets, project rankings, per-assignee workload, comparison periods and CSV export. Select both inclusive date endpoints and limit the range to 366 days. CSV exports are capped at 5,000 rows and include a UTF-8 BOM plus an Excel `sep=,` directive. See [OpenAPI](config/schema.yml) for the full request contract and [task reminders](docs/task-reminders.md) for scheduling, timezones and recovery.

## Deployment and operations

- Run the frontend as a production Next.js build. Use the [infrastructure guide](docs/infrastructure.md) for the non-root Django overlay, Redis, Celery worker, Beat, TLS and release steps. Set explicit allowed hosts, secure cookies and SMTP settings.
- Back up PostgreSQL, avatars and both private attachment stores together. Mount the same media and private file volumes into the API and worker. Keep private attachments outside publicly served media.
- Verification, invitation, and lifecycle jobs use a PostgreSQL outbox. The worker retries transient failures and one Beat recovers due jobs. Run `python manage.py recover_background_jobs` to trigger recovery manually.
- Avatar cleanup jobs commit with the change that retired the file. Workers check references before deleting. Run `python manage.py cleanup_avatar_files` to preview generated orphan files at least 24 hours old. Use `--apply` to queue those files for retryable cleanup. For comments and chats use their respective cleanup commands and follow the [storage recovery procedure](docs/infrastructure.md).
- Session restoration and initial workspace reads have deadlines. If the service is unavailable, the dashboard offers retry and a route back to the website. An expired session goes to login. Unexpected render failures show a localized recovery page.

## Development and verification

| Path | Purpose |
| --- | --- |
| `client/src/` | Next.js routes, UI and API client |
| `config/` | Django apps, backend tests, migrations and settings |
| `client/tests/` and `client/e2e/` | Frontend unit tests and browser scenarios |
| `config/schema.yml` | Generated OpenAPI contract committed with API changes |
| `.github/workflows/tests.yml` | Automated checks on pushes and pull requests |

Run backend checks in the backend container or in the active Python environment from `config/`.

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --fail-on-warn --file schema.yml
python -m pytest -q
```

Run the frontend checks from `client/`.

```sh
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

See [frontend performance, SEO and quality](docs/frontend-quality.md) for the route and cache inventory, bundle analysis, local Lighthouse checks and the pre-commit hook.

For browser verification, use an isolated PostgreSQL database named `teamboard_e2e` and dedicated Redis. Set `POSTGRES_DB`, matching connection details and `E2E_PASSWORD`. Set `E2E_PYTHON` to the virtual environment interpreter if necessary. From `client/` run `npx playwright install chromium` and `npm run test:e2e`. The runner starts Django on port 8100 and the production frontend on port 3100. Set `E2E_BROWSER_CHANNEL=chrome` or `msedge` to use the installed browser.

Browser tests cover locale and theme combinations, desktop and mobile layouts, keyboard and dialog focus, accessible names and automated axe checks, plus retry after session/API/runtime failures and real HTTP 404s. A separate fixture seeds 240 tasks. To record React render durations from the production profiling build, run that browser suite with `NEXT_PUBLIC_TEAMBOARD_PROFILE_UI=1` and the same test services.

CI collects branch coverage from the Django suite and line/branch/function coverage from the TypeScript modules exercised by frontend unit tests. The GitHub workflow publishes Cobertura and LCOV reports and runs a separate dependency audit. For the same reports locally, install `requirements-ci.txt`, run `python -m coverage run -m pytest` and `python -m coverage xml` from `config/`, and run `npm run test:coverage` from `client/`. Audit the Python manifests with `python -m pip_audit -r requirements.txt -r requirements-ci.txt` from the repository root and the locked JavaScript tree with `npm audit --audit-level=moderate` from `client/`. Keep logs, profiling captures and local benchmark data under ignored `artifacts/` and `client/test-results/`.

## License

The application is distributed under the [MIT License](LICENSE). Bundled open font licenses are under `client/public/fonts/open/`. IranSansX is supplied separately under its own license.
