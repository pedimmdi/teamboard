# TeamBoard

TeamBoard is a project management platform in development, built with Django REST Framework and Next.js. It is designed to support team collaboration, task management, and secure account access through a versioned REST API.

The current implementation includes account management, authentication, session security, workspaces, role-based membership, email invitations, projects, and task management on both the API and responsive web dashboard. Tasks include a Kanban board, a paginated list, advanced filters, and atomic ordering.

## Current Features

### Backend

- Custom user model with email-based identification
- User profile management with validated profile image uploads
- Workspace creation, overview, settings, and deletion
- Owner, admin, and member roles with workspace-scoped access
- Member management, ownership transfer, and leaving a workspace
- Email invitations with acceptance, resend, revocation, and expiration
- Workspace-scoped project APIs with manager and member roles
- Global project management for workspace owners and admins
- Project-scoped task creation, retrieval, updates, and deletion
- Task statuses, priorities, assignees, and due dates
- Task filtering, searching, pagination, and ordering
- Kanban task positions and atomic drag-and-drop move operations
- Workspace owner/admin task management without direct project membership
- Project membership validation for task assignees
- PostgreSQL concurrency tests for task reordering
- Database constraints and triggers protecting project membership and manager integrity
- JWT authentication with short-lived access tokens
- Refresh token rotation using an HttpOnly cookie
- Session tracking, session revocation, and active-session management
- Email verification
- Password change and password reset flows
- Request throttling for sensitive authentication endpoints
- Django Admin integration for users, profiles, and sessions
- Versioned REST API
- OpenAPI schema, Swagger UI, and ReDoc documentation

### Frontend

- Next.js App Router with TypeScript
- Account registration and login
- Email verification flow
- Forgot-password and reset-password pages
- Authenticated account dashboard
- Profile editing, image preview, upload and removal
- Profile pictures in workspace member lists and the account sidebar
- Workspace listing, creation, overview, members, invitations, and settings
- Shared workspace navigation icon and distinct role badges on desktop and mobile
- Workspace switcher with role labels, desktop dropdown, and mobile sheet
- Project listing, creation, overview, member management, and settings
- Role-aware project actions, inline validation, and protected-action dialogs
- Task board and list, URL-based filters, sorting, and column pagination
- Responsive task creation, detail editing, assignment, and deletion dialogs
- Desktop drag-and-drop and keyboard/touch task moves with atomic Kanban ordering
- Compact profile image controls with upload and removal in one row
- Password and security settings
- Active session management and session revocation
- Automatic access-token refresh and session handling
- Shared API client and reusable UI components

## Tech Stack

| Area | Technologies |
|---|---|
| Backend | Python 3.14, Django 5.2, Django REST Framework |
| Authentication | Simple JWT, HttpOnly refresh-token cookies |
| Database | PostgreSQL 17 |
| API documentation | drf-spectacular, Swagger UI, ReDoc |
| Frontend | Next.js 16, React 19, TypeScript |
| Code quality | ESLint, TypeScript checks during production builds |
| Containers | Docker, Docker Compose |
| CI | GitHub Actions |

## Project Structure

```text
teamboard/
├── .github/
│   └── workflows/
│       └── tests.yml
├── client/
│   ├── public/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── accept-invitation/
│   │   │   │   ├── forgot-password/
│   │   │   │   ├── login/
│   │   │   │   ├── register/
│   │   │   │   ├── resend-verification/
│   │   │   │   ├── reset-password/
│   │   │   │   └── verify-email/
│   │   │   ├── dashboard/
│   │   │   │   ├── security/
│   │   │   │   ├── sessions/
│   │   │   │   └── workspaces/
│   │   │   │       └── [slug]/
│   │   │   │           ├── members/
│   │   │   │           ├── invitations/
│   │   │   │           └── settings/
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   │   └── ui/
│   │   └── lib/
│   │       ├── api.ts
│   │       └── auth.tsx
│   ├── package.json
│   ├── package-lock.json
│   └── next.config.ts
├── config/
│   ├── accounts/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── serializers.py
│   │   │       ├── urls.py
│   │   │       └── views.py
│   │   ├── migrations/
│   │   ├── admin.py
│   │   ├── authentication.py
│   │   ├── models.py
│   │   ├── validators.py
│   │   ├── tests.py
│   │   └── test_avatars.py
│   ├── workspaces/
│   │   ├── api/v1/
│   │   ├── migrations/
│   │   ├── access.py
│   │   ├── admin.py
│   │   ├── models.py
│   │   ├── services.py
│   │   ├── signals.py
│   │   ├── tests.py
│   │   └── test_migrations.py
│   ├── projects/
│   │   ├── api/v1/
│   │   ├── migrations/
│   │   ├── access.py
│   │   ├── models.py
│   │   ├── services.py
│   │   ├── test_api.py
│   │   ├── test_services.py
│   │   └── test_db_invariants.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── api_v1_urls.py
│   ├── manage.py
│   ├── schema.yml
│   └── pytest.ini
├── docker/
│   ├── backend.Dockerfile
│   └── frontend.Dockerfile
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
├── LICENSE
└── README.md
```

## Prerequisites

For the Docker-based setup, install:

- Git
- Docker Desktop with Docker Compose

For running the frontend directly on your machine, you will also need Node.js 22 and npm.

## Getting Started with Docker

### 1. Clone the repository

```bash
git clone https://github.com/pedimmdi/teamboard.git
cd teamboard
```

### 2. Configure environment variables

Create a local environment file from the example.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace placeholder values, especially `SECRET_KEY` and `POSTGRES_PASSWORD`, with suitable local development values.

The example configuration is intended for local development. Do not reuse its placeholder secrets in a deployed environment, and never commit `.env`.

### 3. Build and start the services

```bash
docker compose up -d --build
```

Check the service status:

```bash
docker compose ps
```

The stack contains three services:

| Service | Purpose | Local address |
|---|---|---|
| `frontend` | Next.js web application | http://localhost:3000 |
| `backend` | Django REST API and admin | http://localhost:8000 |
| `db` | PostgreSQL database | `localhost:5432` |

The service ports are bound to the local machine.

### 4. Apply database migrations

```bash
docker compose exec backend python manage.py migrate
```

Run migrations before using the application against a newly initialized database.

### 5. Create an administrator account

```bash
docker compose exec backend python manage.py createsuperuser
```

Follow the prompts to create the Django administrator account.

### 6. Open TeamBoard

- Frontend: http://localhost:3000
- Django Admin: http://localhost:8000/admin/
- Swagger UI: http://localhost:8000/api/docs/
- OpenAPI schema: http://localhost:8000/api/schema/
- ReDoc: http://localhost:8000/api/redoc/

The root frontend route redirects to the login page.

## Running the Frontend Locally

To run Next.js outside Docker while keeping the backend and database in Docker, first start the stack and apply migrations as described above.

Stop the Docker frontend service to free port 3000:

```bash
docker compose stop frontend
```

Then open a separate terminal:

```powershell
cd client
npm ci
npm run dev
```

Open http://localhost:3000.

The frontend reads `NEXT_PUBLIC_API_URL` at build time, with `http://localhost:8000` as its fallback. For local development, that default points to the Django API exposed by Docker.

To validate the frontend before committing changes:

```bash
cd client
npm ci
npm run lint
npm test
npm run build
```

The production build includes TypeScript validation.

## API Overview

All application API endpoints are currently versioned under `/api/v1/`.

### Accounts and authentication

| Functionality | Endpoint |
|---|---|
| Registration | `POST /api/v1/accounts/register/` |
| Login | `POST /api/v1/accounts/login/` |
| Refresh access token | `POST /api/v1/accounts/refresh/` |
| Logout | `POST /api/v1/accounts/logout/` |
| Retrieve or update current user | `GET/PATCH /api/v1/accounts/me/` |
| List sessions | `GET /api/v1/accounts/sessions/` |
| Revoke other sessions | `POST /api/v1/accounts/sessions/revoke-others/` |
| Revoke a specific session | `DELETE /api/v1/accounts/sessions/<session_id>/` |
| Change password | `POST /api/v1/accounts/password/change/` |
| Request password reset | `POST /api/v1/accounts/password/reset/` |
| Confirm password reset | `POST /api/v1/accounts/password/reset/confirm/` |
| Verify email | `POST /api/v1/accounts/email/verify/` |
| Resend verification email | `POST /api/v1/accounts/email/resend/` |

Use Swagger UI to inspect request payloads, supported HTTP methods, authentication requirements, and response schemas.

### Workspaces, members, and invitations

| Functionality | Endpoint |
|---|---|
| List or create workspaces | `GET/POST /api/v1/workspaces/` |
| Retrieve, update, or delete a workspace | `GET/PATCH/DELETE /api/v1/workspaces/<slug>/` |
| List members | `GET /api/v1/workspaces/<slug>/members/` |
| Update a member's role | `PATCH /api/v1/workspaces/<slug>/members/<membership_id>/role/` |
| Remove a member | `DELETE /api/v1/workspaces/<slug>/members/<membership_id>/` |
| Transfer ownership | `POST /api/v1/workspaces/<slug>/transfer-ownership/` |
| Leave a workspace | `POST /api/v1/workspaces/<slug>/leave/` |
| List or send invitations | `GET/POST /api/v1/workspaces/<slug>/invitations/` |
| Revoke an invitation | `DELETE /api/v1/workspaces/<slug>/invitations/<invitation_id>/` |
| Resend an invitation | `POST /api/v1/workspaces/<slug>/invitations/<invitation_id>/resend/` |
| Accept an invitation | `POST /api/v1/workspaces/invitations/accept/` |

Workspace members can access their workspace overview and member list. Owners and
admins can edit workspace settings and manage invitations. Only owners can change
roles, transfer ownership, or delete a workspace. Owners can remove admins and
members; admins can remove members only. Owners must transfer ownership before
leaving a workspace.

The dashboard uses `/dashboard` for profiles, `/dashboard/security` for password
settings, `/dashboard/sessions` for sessions, and `/dashboard/workspaces` for
workspaces. Selecting a workspace opens its projects. The sidebar provides Projects,
People, and Settings; the workspace switcher retains access to all workspaces.
The same navigation remains visible on profile, security, and session pages.
The last workspace selection is remembered per account for the current browser
session and checked against the API before restoring it. An unavailable saved
workspace falls back to an accessible workspace; accounts without workspaces see
disabled workspace links and can create one through the switcher. Mobile account
pages include Profile, Security, Sessions, and sign-out controls above the content.
Invitation links preserve the acceptance flow through login or registration.

### Projects

Project endpoints are nested under `/api/v1/workspaces/<slug>/projects/`.

| Functionality | Method and relative path |
|---|---|
| List accessible projects / create a project | `GET/POST /` |
| Retrieve / edit / delete a project | `GET/PATCH/DELETE /<project_id>/` |
| Leave a project | `POST /<project_id>/leave/` |
| List / add project members | `GET/POST /<project_id>/members/` |
| Change a project role | `PATCH /<project_id>/members/<membership_id>/role/` |
| Remove a project member | `DELETE /<project_id>/members/<membership_id>/` |

| Actor | Access |
|---|---|
| Workspace owner or admin | See every project in their workspace; create, edit, delete, add/remove members, and assign managers without personal project membership |
| Project manager with regular workspace membership | See and edit their projects; add/remove regular project members; cannot assign manager roles or delete projects |
| Project member | See their projects and member lists; leave their project |
| Other workspace member / outsider | No access to the project's details or membership endpoints |

Global management access does not create a project membership: the response's
`role` reports the actual project membership and may be `null` for a workspace
owner or admin. Leaving a project removes a personal membership; it does not
revoke the global permissions of workspace owners or admins.

The dashboard lives at `/dashboard/workspaces/<slug>/projects`. Each project has
Overview, Members, and Settings screens. Owners and admins see all workspace
projects; regular members see only their assigned projects. Manager, Member, and
Admin access badges reflect personal membership and inherited access. Desktop
tables become cards on smaller screens, with mobile sheets for forms and actions.
Project creation and editing validate names and the 5000-character description;
deletion requires entering the exact project name. Protected actions display the
API explanation and offer a route to manage members where appropriate. The
overview links directly to the project's task board.

Project names are unique within their workspace, ignoring case. Names allow
150 characters and descriptions allow 5000 characters. Permission checks precede
validation for updates and role changes. Ordinary members receive 403 for forbidden
operations; inaccessible projects return 404 even for invalid request bodies.

Every project requires at least one actual manager who belongs to its workspace.
The final manager cannot leave, be removed, or be demoted until a replacement is
assigned. Workspace removal and leave return 409 with
`Assign another manager before removing this user from the workspace.`
The frontend displays this `detail` message directly. Owners and admins can resolve
the conflict by assigning another manager without first joining the project.

Database triggers also reject project members outside the workspace and serialize
membership writes against workspace departure. Invalid roles and relationship
transfers are rejected by database constraints. Known constraint conflicts and
retryable database concurrency failures return 409; unexpected database errors
remain server errors rather than being disguised as validation failures.

### Tasks and Kanban

Task endpoints are nested under:

`/api/v1/workspaces/<slug>/projects/<project_id>/tasks/`

| Functionality | Method and relative path |
|---|---|
| List tasks / create task | `GET/POST /` |
| Retrieve / update / delete task | `GET/PATCH/DELETE /<task_id>/` |
| Move or reorder task | `POST /<task_id>/move/` |

Tasks support four statuses: `todo`, `in_progress`, `in_review`, and `done`.

Each task has a zero-based `position` within its project and status column. The move endpoint accepts a target `status` and `position`:

```json
{
  "status": "in_progress",
  "position": 0
}
```

Moving a task updates the ordering of affected columns inside a database transaction. Creating, deleting, or changing the status of a task also maintains Kanban positions.

For concurrent editing, send `before_task` (a destination task UUID) instead of
`position`, or `placement: "first"` / `placement: "last"` for a column boundary.
Send exactly one target selector together with `status`. The server resolves the
target under the same project lock as the move, so intervening reorders or
inserts do not invalidate the intended placement. A missing destination returns
404; a destination that changed columns returns 400 without moving the task.
Numeric `position` remains supported for existing clients.

Task listing supports filtering by status, priority, assignee, due date, and overdue state, as well as text search and ordering. Use `ordering=position` together with a status filter to retrieve a Kanban column in position order.
Overdue means a due date before the current UTC calendar day, excluding completed
tasks. The dashboard uses the same UTC day as the API.

Workspace owners and admins can manage tasks without joining each project. Regular workspace members require project membership. Task assignees must be actual members of both the project and its workspace; inherited management access alone does not make a user eligible for assignment.

Task responses include assignee and creator email addresses and avatar URLs when available.

The task dashboard lives at `/dashboard/workspaces/<slug>/projects/<project_id>/tasks`.
It includes a four-column desktop Kanban board, a status-column view on smaller
screens, and a paginated list with sortable columns and mobile cards. Each board
column loads independently and offers Show more for remaining tasks. Dragging a
card changes its status or position through the atomic move endpoint; the Move
task menu offers the same operation with keyboard and touch controls, including
moving to the beginning or end of a complete column.
Moves send a destination task or column boundary for the server to resolve
atomically; failures keep the server explanation visible while the board refreshes.
Show more failures leave loaded cards visible and offer Retry in the affected
column without hiding the board or changing the successful page.

Search, status, priority, assignee, overdue, due-before, list ordering, and the
selected view are stored in the URL. Assignee filters support Anyone, Me,
Unassigned, and individual project members. Board order is manual; list order is
independent. The task detail drawer is linkable with `?task=<task_id>` and becomes
a full-screen form on mobile. Creation uses a desktop dialog or mobile sheet.
Descriptions allow 10000 characters and titles allow 200. Clearing an assignee or
due date sends an explicit null, while edits submit only changed fields.

Every user with project access can create, edit, and move tasks. Only project
managers and workspace owners/admins can delete them. Assignee selection loads all
pages of actual project members, so inherited management access does not offer an
Assign to me option unless the user is also a project member. Validation and API
errors remain visible in the relevant form; missing tasks offer Back to tasks.

## Authentication

Protected API endpoints use JWT bearer authentication.

Include the access token in the request header:

```http
Authorization: Bearer <access_token>
```

Access tokens are short-lived. The refresh token is stored in an HttpOnly cookie and is not directly accessible to frontend JavaScript. The frontend can request a fresh access token through the refresh endpoint when restoring a session or recovering from an expired access token.

The backend also associates authenticated requests with tracked user sessions, allowing revoked or expired sessions to be rejected.

## Email Configuration

The default email backend is Django's console email backend. During local development, outgoing messages are written to backend logs instead of being delivered to a real inbox.

This supports development and testing of email-related flows without an external email provider. Configure an appropriate email service before deploying the application.

## Running Tests

### Backend

Run the full backend suite against PostgreSQL in the Docker environment:

```bash
docker compose exec backend python -m pytest -v
```

The suite covers accounts, session security, profile images, workspace and project
permissions, memberships, invitations, direct database constraints, concurrent
mutations, admin deletion protection, schema consistency, and upgrades from the
former workspace app name.
Run the checks used by CI before committing:

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py spectacular --validate --fail-on-warn --file /tmp/teamboard-schema.yml
```

### Frontend

Run API-client and permission tests, lint, and production build checks:

```bash
cd client
npm ci
npm run lint
npm test
npm run build
```

### Continuous integration

GitHub Actions runs on pushes, pull requests, and manual workflow dispatches.

The current workflow contains two independent jobs:

- **Backend:** installs Python dependencies, starts PostgreSQL, checks Django configuration and migration consistency, validates the OpenAPI schema, and runs the full pytest suite.
- **Frontend:** installs Node.js dependencies using `npm ci`, runs ESLint and the frontend tests, and builds the Next.js application.

Browser end-to-end tests are not currently part of the workflow.

## Useful Docker Commands

Start all services:

```bash
docker compose up -d
```

Rebuild and start all services:

```bash
docker compose up -d --build
```

View service status:

```bash
docker compose ps
```

Follow backend logs:

```bash
docker compose logs -f backend
```

Follow frontend logs:

```bash
docker compose logs -f frontend
```

Open a Django shell:

```bash
docker compose exec backend python manage.py shell
```

Stop services:

```bash
docker compose down
```

Stop services and delete the database volume:

```bash
docker compose down -v
```

**Warning:** `docker compose down -v` deletes the PostgreSQL volume and its stored database data. Only use it when you intentionally want to remove that data.

## Development Roadmap

Account security, profile images, workspaces, projects, tasks, memberships, and invitations are
implemented. Planned development includes:

- Additional collaboration features
- Automated browser end-to-end testing

The task management API and frontend are implemented and tested. Additional collaboration features remain planned.

## Development and Deployment Notes

- The current Docker backend uses Django's development server.
- The example environment configuration is for local development only.
- Production deployment requires an appropriate production application server, secure secret management, HTTPS, production cookie settings, and suitable host and CORS configuration.
- Configure production email delivery, logging, static assets, database backups, and monitoring before deployment.
- Review security and deployment settings before exposing services publicly.
- Never commit `.env`, real credentials, passwords, access tokens, or other secrets.

## Workspace rename upgrades

The backend app and API now use `workspaces`; the dashboard lives at
`/dashboard/workspaces` and the API at `/api/v1/workspaces/`.
Run `python manage.py migrate` before starting the updated backend.
The replacement migration recognizes the three previously applied migrations
of the former app, then renames its tables and foreign keys in place. Existing
workspace IDs, slugs, memberships, invitations, content types and permission
assignments are retained. Historical names remain only in upgrade migrations
and their regression test. Upgrade databases from the previous release with all
three former app migrations applied; do not fake or delete migration records.

## Profile images

Install the updated requirements (or rebuild the backend Docker image), then run
`python manage.py migrate`. Authenticated users can upload an `avatar` with a
multipart PATCH to `/api/v1/accounts/me/`, or remove it with JSON
`{"avatar": null}`. Omitting the field keeps the current image.
JPEG, PNG and WebP images are accepted up to 5 MB and 4096 × 4096 pixels.
New images are re-encoded before storage, with orientation applied and EXIF,
location, author and other source metadata removed. The same normalization runs
for API and admin uploads. Uploads are limited to 10 per hour per authenticated
user; reading a profile, editing names, and removing an image do not consume that
upload allowance. Excess uploads return 429.
The account API, workspace member API, and project member API return the image URL or `null`.
Replaced images and deleted profiles are cleaned up after database commit.
The admin deletion confirmation protects workspace owners and the final project
managers, including when selecting multiple users. Transfer ownership or assign
replacement managers first. A concurrent protection failure produces an admin
message rather than a server error.

Uploads are stored in `config/media/`, which is ignored by Git and persists
through the existing Docker bind mount. Django serves `/media/` when `DEBUG=True`.
For production, serve `MEDIA_ROOT` at `/media/` through the deployment's media
server or configure Django storage, and preserve uploaded files across deploys.

## Commit convention

Use `type(scope): description`, with the affected app or area as the scope.
Examples: `feat(workspaces): add workspace settings`,
`fix(accounts): refine profile picture controls`, and
`docs(readme): update development instructions`.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
