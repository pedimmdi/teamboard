# TeamBoard

TeamBoard is a project management platform in development, built with Django REST Framework and Next.js. It is designed to support team collaboration, task management, and secure account access through a versioned REST API.

The current implementation focuses on account management, authentication, session security, and the frontend foundation. Workspace, team, and task management modules are planned for subsequent development.

## Current Features

### Backend

- Custom user model with email-based identification
- User profile management
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
- Profile editing
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
│   │   │   │   ├── forgot-password/
│   │   │   │   ├── login/
│   │   │   │   ├── register/
│   │   │   │   ├── reset-password/
│   │   │   │   └── verify-email/
│   │   │   ├── dashboard/
│   │   │   │   ├── security/
│   │   │   │   └── sessions/
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
                ├── serializers.py
│   │   │       ├── urls.py
│   │   │       └── views.py
│   │   ├── migrations/
│   │   ├── admin.py
│   │   ├── authentication.py
│   │   ├── models.py
│   │   └── tests.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── api_v1_urls.py
│   ├── manage.py
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
| Verify email | `GET /api/v1/accounts/email/verify/` |
| Resend verification email | `POST /api/v1/accounts/email/resend/` |

Use Swagger UI to inspect request payloads, supported HTTP methods, authentication requirements, and response schemas.

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

Run the account tests in the Docker environment:

```bash
docker compose exec backend python -m pytest accounts/tests.py -v
```

Alternatively, use Django's test runner:

```bash
docker compose exec backend python manage.py test
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

- **Backend:** installs Python dependencies, starts PostgreSQL, and runs `accounts/tests.py`.
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

The current foundation focuses on account security and the frontend/backend architecture. Planned development includes:

- Workspace and organization management
- Team membership and role-based permissions
- Project and task management
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

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
