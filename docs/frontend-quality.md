# Frontend performance, search and quality

## Rendering and caching

| Routes | Rendering | Data and freshness |
| --- | --- | --- |
| `/`, `/about`, `/terms` and their `/fa` equivalents | Server-rendered, with client controls for preferences and signed-in navigation | About and Terms use static copy. Home reads three public articles through the bounded 60-second list cache. |
| Contact and Privacy in both languages | Server-rendered, with the contact form interactive in the browser | The retention policy is cached for 60 seconds and the UI handles a failed policy request. Submissions are sent directly to Django. |
| Blog lists and articles in both languages | Server-rendered | List responses live for 60 seconds. Details live for 30 seconds. Keys separate language, page and slug. Failed reads can be retried. |
| Authentication and invitation flows | Server-rendered locale and theme shell, with client forms | Form operations and session restoration use the API at interaction time. |
| Dashboard and all workspace, project and account pages | Server-rendered shell and interactive client views | API reads are scoped to the current authenticated account and workspace. Session and permission data have no shared result cache. |
| Icons, Open Graph image and `robots.txt` | Prerendered by Next.js | Rebuilt when the app changes. |
| `sitemap.xml` | Dynamic metadata route | A complete result stays fresh for five minutes. The last complete snapshot can be served for up to an hour on upstream failure. Known public pages remain available after a cold failure. |

The root layout reads the selected theme and locale before rendering HTML. Full-page SSG or ISR would require changing that preference boundary. Anonymous editorial data already has a short revalidation window, separately from personalized HTML. A publishing action takes effect in Django immediately and may take up to the relevant TTL to appear in the public frontend. The App Router has no app-owned JSON route handlers. Public data reads and error states are handled by the credential-free reader and Django API.

## Bundle, images and fonts

`npm run analyze -- --snapshot <name>` writes a Turbopack module graph under `client/.next/diagnostics/analyze`. `npx next analyze export --snapshot <name>` emits it as JSON Lines. Both commands use the Next.js version in the lockfile and the project's normal bundler.

The Tasks route's initial JavaScript went from 684,012 to 662,806 bytes, or from 207,747 to 203,317 bytes with gzip measured per chunk. The measurement deduplicates files across Next.js's root and App Router entry manifests. Comments and reminders now download when the task drawer opens. Home, Blog, Login and Reports stayed within 100 gzip bytes of baseline. These are build measurements and exclude request overhead, HTML and data transfers.

Public copy and Markdown render on the server. Reports use local components and CSS for charts. The project ships no general-purpose UI library or third-party analytics, chat widget or tag-manager scripts. The first-party chat uses the project's API and live connection.

The UI uses local vector artwork. Raster avatars use explicit dimensions through `next/image` and the upload pipeline encodes new files as WebP. Private attachment previews use user-authorized blob URLs and open on demand. Inter loads through `next/font/local` with preload. Persian HTML also preloads the installer-managed regular IranSansX face or the bundled Vazirmatn fallback. Older manual font installations load through CSS. Licensed font files remain installed separately.

## Search and accessibility

Public pages have localized titles, descriptions, canonical URLs, Open Graph and Twitter Card metadata. Page one of the blog and the paginated lists use their respective canonical URLs. Translated articles have language alternates and independent canonicals. A Persian link to an English-only article points its canonical to English and opts out of indexing. Articles with empty excerpts receive localized descriptions. The home page includes WebApplication structured data, and published articles include BlogPosting and breadcrumb structured data.

Public navigation uses Next.js links and includes a skip link, semantic landmarks and page headings. Social images and user avatars have text alternatives. The sitemap lists indexable public routes and translated articles. `robots.txt` and response headers describe the crawl policy for account operations and private routes.

Measure the SEO category against the local built app with representative English and Persian home, blog, article and contact pages. For example, from the frontend directory:

```sh
npx lighthouse http://localhost:3100/fa --only-categories=seo --output=json --output-path=../artifacts/lighthouse-fa.json
```

Use `--preset=desktop` for the desktop run. The target is above 90 in each run. GitHub's browser suite separately checks real 404s, canonical and language links, website navigation, accessibility and both localized layouts.

## Quality gates

- Django unit and DRF API tests cover validation, authorization, registration, verification, password recovery and other core operations. Postgres and Redis integration tests exercise real database and live-event behavior. TeamBoard has no payment flow.
- Playwright covers task and workspace workflows, chat, notification and session recovery, public pages and account preferences. The suite includes desktop and mobile viewports, keyboard interaction and automated accessibility checks.
- CI requires at least 85% combined line and branch coverage across the core account, background, project, task and workspace apps. It requires 70% line coverage across frontend modules exercised by the unit suite. Browser coverage is reported through test scenarios.
- The frontend runs ESLint and strict TypeScript checks. The repository includes a lightweight pre-commit hook that checks staged whitespace. Run `git config core.hooksPath .githooks` in this checkout to enable it. On a shell that requires executable file permissions, run `chmod +x .githooks/pre-commit` first.

## User flows and recovery

- Next.js provides localized unmatched-route, route-error and global-error surfaces. Dashboard recovery tests exercise real 404s, stalled session restoration, API errors and runtime errors. API errors generated before or outside DRF return safe JSON in Django's normal error mode.
- Boards, lists, inbox, chat, calendars and reports expose operation-specific loading, empty and recovery states. Task actions use transient feedback. Forms use inline status and error feedback where it stays close to the related field or operation.
- The contact form has client validation and field-error mapping from Django. A network failure or 15-second deadline restores the submit control and preserves the entered text. Registration, verification and password reset use server validation and are covered by the account integration suite.
- Persian paths and preferences set direction, theme, formatting locale and calendar behavior. Calendar dates and stored time instants retain their separate semantics. The browser matrix exercises English and Persian, both themes and narrow and wide viewports.
