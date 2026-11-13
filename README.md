# TeamBoard

TeamBoard is a workspace for planning projects, tracking tasks on a Kanban board, and discussing work in context. It pairs a Next.js frontend with a Django REST API and PostgreSQL.

## Features

- **Accounts** with email verification, password reset, profile images, and session management.
- **Workspaces** with invitations, ownership transfer, member management, and workspace images. Owner, Admin, and Member badges use green, purple, and blue respectively.
- **Projects** with membership, project images, and Board and List views. Board is the default and the browser remembers the selected view.
- **Tasks** with four Kanban columns, drag-and-drop, assignees, priorities, due dates, and filters. Open a card to see its discussion and details.
- **Comments** with replies, project-member mentions, editing, moderation, attachment downloads, and counts on task cards.

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
docker compose exec backend python manage.py showmigrations comments
```

If the Comments tab repeatedly reports a generic error, check the backend logs and confirm that `comments.0003_private_attachment_storage` is marked applied. Retry the tab after the backend is ready.

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

Workspace Owners and Admins can manage project access across the workspace. Project Managers can manage the projects they belong to. Project Members can work on tasks and participate in discussions within projects they can access.

A comment request accepts `body` and optional `reply_to`. Send multipart form data to include one `attachment`. Use `@` in the composer to select a project member. Authors can edit their own comments. Managers and workspace administrators can moderate comments. Download an attachment through the authenticated `<comment_id>/attachment/` endpoint.

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

Create an isolated PostgreSQL database named `teamboard_e2e` and set `POSTGRES_DB=teamboard_e2e` and `E2E_PASSWORD` in the test process environment. Use the matching PostgreSQL credentials and a Django environment with the project dependencies installed. Set `E2E_PYTHON` to the virtual environment's Python executable if needed. From `client/` run `npx playwright install chromium` and `npm run test:e2e`. For an installed Chrome or Edge, set `E2E_BROWSER_CHANNEL` to `chrome` or `msedge`.

Playwright starts Next.js on port 3100 and Django on port 8100. The test server applies migrations and seeds a verified user in the isolated database. The tests exercise the browser, API and PostgreSQL together. GitHub Actions runs the Chromium suite and saves failure traces.

## License

TeamBoard is distributed under the [MIT License](LICENSE).
