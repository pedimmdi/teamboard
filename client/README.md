# TeamBoard frontend

This package contains the Next.js App Router interface for TeamBoard. See the [project README](../README.md) for Docker setup, API configuration, Persian fonts and deployment.

## Run locally

With Django and its services running, install the locked dependencies and start Next.js.

```sh
npm ci
npm run dev
```

The default browser origin is `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` for the browser and `WEBSITE_API_URL` for server-side public reads. Set `NEXT_PUBLIC_SITE_URL` to the public HTTPS origin before a production build.

## Verify

```sh
npm run lint
npm run test:coverage
npm run build
npm run test:e2e
```

The browser suite requires the isolated backend and environment described in the [browser setup](../README.md#development-and-verification). It covers both locales and themes, account and workspace flows, accessible forms and dialogs, and recovery from navigation and service failures. The unit runner writes LCOV under `coverage/`.

Use `NEXT_PUBLIC_TEAMBOARD_PROFILE_UI=1` for an opt-in production React profile of the 240-task browser fixture. See the [measurement notes](../docs/performance.md).
