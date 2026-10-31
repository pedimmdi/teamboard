# TeamBoard

TeamBoard is a project management platform in development, built with Django REST Framework and Next.js. It is designed to support team collaboration, task management, and secure account access through a versioned REST API.

The current implementation includes account management, authentication, session security, workspaces, role-based membership, email invitations, and project APIs. Task management is the next development area; project screens are not implemented in the frontend yet.

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
workspaces. Each workspace has overview, members, invitations, and settings tabs.
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

The suite covers accounts, session security, profile images, workspace permissions,
memberships, invitations, and upgrades from the former workspace app name.
Run the checks used by CI before committing:

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py spectacular --validate --fail-on-warn --file /tmp/teamboard-schema.yml
```

### Frontend

Run lint and production build checks:

```bash
cd client
npm ci
npm run lint
npm run build
```

### Continuous integration

GitHub Actions runs on pushes, pull requests, and manual workflow dispatches.

The current workflow contains two independent jobs:

- **Backend:** installs Python dependencies, starts PostgreSQL, checks Django configuration and migration consistency, validates the OpenAPI schema, and runs the full pytest suite.
- **Frontend:** installs Node.js dependencies using `npm ci`, runs ESLint, and builds the Next.js application.

Integration and end-to-end browser tests are not currently part of the workflow.

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

Account security, profile images, workspaces, projects, memberships, and invitations are
implemented. Planned development includes:

- Project screens and task management
- Collaboration features
- Integration and end-to-end testing

These are planned capabilities, not claims that those modules are already implemented.

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
The account API and workspace member API return the image URL or `null`.
Replaced images and deleted profiles are cleaned up after database commit.

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
