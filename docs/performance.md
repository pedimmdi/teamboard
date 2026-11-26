# Measured performance review

## Database and cache audit

This review uses disposable PostgreSQL 17 fixtures and checks the same endpoint responses and access scopes before and after changes. The detailed SQL probes measure result-set bytes separately from the JSON response. Existing query-budget tests cover single-item and full-page reads.

| Area | Result |
| --- | --- |
| N+1 and serializers | Related rows are joined or prefetched according to the data each serializer accesses. Query budgets cover task comment counts, timeline rows, the dashboard, notifications and chat. The Django Debug Toolbar SQL panel ran against temporary benchmark fixtures as a separate diagnostic. |
| Heavy projections | Dashboard result sets fell from 213,946 to 7,362 bytes. Calendar timeline result sets fell from 2,520,954 to 26,454 bytes. Inbox rows fell from 173,271 to 5,656 bytes and chat message rows from 159,480 to 6,089 bytes. The clients receive the same response fields. |
| Aggregation | On 10,000 tasks and 40,000 comments, the default task paginator count went from a 24.66 ms to a 1.47 ms median. Its 20-row data query went from 77.71 ms to 0.31 ms over seven PostgreSQL probes. Comment counts come from the database for rows on the requested page. Report overview uses five queries for a project and four for a workspace, down from seven and six respectively. |
| Pagination | Session and direct conversation inventories use 20 per page by default, with a maximum of 100. Existing clients requesting a bare array receive up to 100 records, `X-Total-Count`, and a `Link` header when another page exists. The workload report returns one grouped row per assignee, and unread counts and overview arrays retain their scoped summary contracts. |
| Indexes and migrations | The measured paths use existing indexes. Schema validation and migration drift checks cover the updated app. |
| Slow-query diagnostics | `benchmark_reads` reports the maximum observed execution duration, SQL shape repetition within one request and the number of executions above the configured threshold across all samples. `--explain` summarizes the longest execution per slow SELECT shape. The output contains counts and selected plan attributes. |
| Redis, sessions and TTLs | Redis supplies live-event transport, the shared throttle cache and Celery. The Redis cache defaults to 300 seconds. Django sessions and the durable outbox use PostgreSQL. The public editorial and sitemap caches retain their explicit TTLs and recovery behavior below. Publishing, updating or unpublishing is reflected in the API immediately after commit. Cached public frontend reads refresh within their TTL. |
| Worker scope | Email delivery and retryable file cleanup use Celery. Upload validation and avatar encoding return their result in the request. Reports use grouped SQL. The project ranking and CSV export apply explicit output limits. |
| Deployment | Database backup scheduling and restoration policy, connection pool sizing, reverse-proxy compression and upload limits, and ASGI worker sizing belong in the deployment phase. Django's ASGI guidance places connection reuse in a pool and keeps `CONN_MAX_AGE=0`. [Django database documentation](https://docs.djangoproject.com/en/5.2/ref/databases/#persistent-connections) |

Run the diagnostic from `config/` against a disposable migrated database:

```sh
python manage.py benchmark_reads --tasks 10000 --projects 10 --repeats 5 --extended --slow-query-ms 100 --explain
```

Repeated query shapes are leads to inspect. Distinct bound parameters can represent legitimate permission checks or aggregates. Query durations are local observations. The command rolls back fixture rows and refreshes the planner statistics for the tables it measured. [Django database instrumentation](https://docs.djangoproject.com/en/5.2/topics/db/instrumentation/)

The 12-endpoint run while other local tests were active recorded two project-ranking executions at or above 100 ms, with a maximum of 141.81 ms. The captured plan aggregated task rows across all 10 projects. An isolated five-repeat run peaked at 23.16 ms on the ranking query and had zero SQL executions at or above 100 ms across the same endpoints.

## Dashboard and Tasks render profile

The browser fixture seeds 240 assigned tasks across four statuses. The production React profiling build records render durations for the dashboard shell and its active page. The workflow opens the dashboard, navigates to the task board, opens a dialog and uses the keyboard to close it.

| Test viewport and appearance | Dashboard commits / p95 | Projects and Tasks interaction commits / p95 |
| --- | ---: | ---: |
| 1440 px, English light | 9 / 8.3 ms | 17 / 18.5 ms |
| 390 px, Persian dark | 9 / 7.4 ms | 17 / 10.6 ms |

These local Chromium samples include navigation and dialog updates. The 18.5 ms maximum in the desktop task flow came from a single commit. The traces support keeping the existing page structure. Run the profile with `NEXT_PUBLIC_TEAMBOARD_PROFILE_UI=1` and `npm run test:e2e -- e2e/ui-quality.spec.mjs`. The profiling build and measurements are opt-in.

Measurements: local Docker Desktop / PostgreSQL 17, November 2026. Raw logs and JSON are kept locally in ignored `artifacts/`, never in the repository. Values are observations, not production SLAs. Read benchmarks use disposable fixtures with rollback and representative planner statistics.

## Earlier baseline measurements

`docker compose exec backend python manage.py benchmark_reads --tasks 10000 --projects 10 --repeats 5 --explain`

| Authorized endpoint | Median ms | Queries |
| --- | ---: | ---: |
| Projects | 7.42 | 4 |
| Historical reports, 90 days | 32.49 | 8 |
| Workload | 8.94 | 2 |
| Project comparison | 28.68 | 3 |
| Calendar, seven days | 28.82 | 4 |

These measurements found no slow plans and supported the existing indexes and cache policy. The latest audit above uses larger payloads and additional endpoint fixtures.

Idle container observations: backend approximately 193 MiB, PostgreSQL 88 MiB, worker 207 MiB, Beat 106 MiB, Redis 5.6 MiB. The frontend development server used approximately 2.2 GiB after extended development; this is not a production server measurement. Worker/Redis/PostgreSQL configuration was left unchanged: idle data does not justify tuning concurrency or memory limits.

Baseline standalone frontend build: approximately 11.62 seconds on this machine. Chunk inventory is recorded in `artifacts/benchmarks/bundle.json`; it is the sum of every build chunk, **not** first-load JavaScript for any route. Production Core Web Vitals require real-user traffic or controlled browser traces; no unsupported LCP/INP improvement is claimed.

## Test execution: measured bottleneck

Controlled Accounts run: 105 tests / four subtests, **77.42 s before**, **7.84 s after** (about 90% lower). Profiled password-heavy tests repeatedly spent 1.4–1.9 seconds creating/verifying fixture passwords. Pytest now uses a fast fixture-only hasher. Production settings, validators, sessions and JWT handling are unchanged. An explicit PBKDF2 authentication test still exercises the production algorithm.

The complete post-change run, including real Redis and a separate worker, passed 968 tests and 182 subtests in 103.36 seconds. The preceding complete baseline log took 1338.88 seconds for 965 tests; because three tests were subsequently added, treat that comparison as overall operational evidence, not a perfectly identical microbenchmark.

Set `TEAMBOARD_FAST_TEST_HASHERS=0` to run with the configured production hashers. CI jobs already run backend, frontend and browser independently. No additional parallel database workers were introduced: migration and locking tests need isolation. No unrelated build step was removed.

## Files and article availability

All Django tests now live inside their app's `tests/` package. Shared Redis integration tests live in `config/tests/`. Relative fixture imports and the cross-app worker helper import were updated. The collected regression suite verifies that tests were not lost during the move.

The running frontend container had been created before `WEBSITE_API_URL` was added. It tried a browser-facing localhost address from inside Docker; the database contained one public article but the frontend could not reach it. Recreating the frontend with the existing Compose environment, and refreshing its dependency volume, returned **HTTP 200 / one public article** from the internal API. The actual `/blog` page then returned 200 with article links and without the load-error message. No publication rules or article permissions were relaxed.

For an existing development dependency volume after pulling new npm dependencies:

```sh
docker compose stop frontend
docker compose run --rm --no-deps frontend npm ci
docker compose up -d --no-deps frontend
```

`WEBSITE_API_URL` is server-reachable (`http://backend:8000` inside Compose); `NEXT_PUBLIC_API_URL` is browser-reachable. Do not use the browser's localhost endpoint as the server-side Docker address.

### Public blog queries and caching

The PostgreSQL comparison used the same 50 published, translated articles before and after the projection change. Each had a 39,600-byte English body and a 45,600-byte Persian body. SQL counts came from Django's `CaptureQueriesContext` during anonymous API calls. Database result bytes came from replaying each captured `SELECT` with `COPY (...) TO STDOUT (FORMAT binary)`, including the `COPY` framing. HTTP bytes are the raw JSON response body without compression or headers. These measurements describe the fixture rather than production latency.

| Public read | SQL queries before → after | Database result bytes before → after | HTTP body bytes before → after |
| --- | ---: | ---: | ---: |
| English list, 50 articles | 2 → 2 | 2,291,556 → 6,156 | 12,952 → 12,952 |
| Persian list, 50 articles | 2 → 2 | 2,291,556 → 7,506 | 14,302 → 14,302 |
| English article | 1 → 1 | 85,455 → 39,747 | 39,870 → 39,870 |
| Persian article | 1 → 1 | 85,455 → 45,774 | 45,897 → 45,897 |
| Sitemap data for 50 articles | 2 → 1 | 2,291,556 → 3,271 | 12,952 → 7,091 |

List and detail projections compute translation availability in SQL. Lists return only card fields, and detail returns the requested language or the English fallback. The sitemap projection returns slug, timestamps and translation availability, with cursor pages of 250 records. Regression tests assert constant query counts, including a second sitemap page when articles share the same publication time.

Next.js caches only the server-side responses of anonymous editorial and policy GET requests. In each process, listing reads are retained for 60 seconds (64 entries), article reads for 30 seconds (128 entries), and the public contact policy for 60 seconds (one entry). An automated test confirms 20 concurrent reads of the same article and language share one upstream request. Locale, pagination and slug are part of the read keys. Failed reads and 404s are fetched again on the next attempt. Editorial edits or unpublishing propagate after these short TTLs.

The sitemap caches a complete successful snapshot for five minutes. It can serve the last complete snapshot for up to one hour from its creation during an upstream outage. A failed refresh waits 15 seconds before trying again. A cold start or expired snapshot serves the known public routes in both languages. The full upstream traversal has a 10-second deadline. These caches are process-local, so a restart starts with an empty cache and multiple replicas can refresh independently. Personalized HTML, cookies, auth responses, contact submissions and workspace data are outside this cache.

## Selected avatar encoder

The actual UI renders avatars at 30–64 CSS pixels. New uploads are capped at 512 pixels on their longest side, keeping substantial high-DPI headroom without changing layout. The existing 5 MiB / 4096-pixel input checks still run first. EXIF orientation is applied, metadata removed, RGB photos encoded as quality-90 WebP, and transparent images encoded losslessly. Existing files are not migrated; replacement/deletion still uses the existing committed-file lifecycle. Attachments never enter this encoder.

Paired three-run medians, identical input bytes in one process (three existing local avatars; no private filenames or contents recorded in this document):

| Sample | Previous stored bytes | New bytes | Previous processing ms | New processing ms |
| --- | ---: | ---: | ---: | ---: |
| 1 | 742,427 | 29,010 | 110.53 | 74.32 |
| 2 | 315,720 | 19,326 | 72.12 | 69.03 |
| 3, transparent | 1,698,481 | 286,704 | 529.74 | 115.86 |

These samples show 83–96% lower stored/transfer bytes. This is a small local sample, not a universal compression ratio. The earlier 1024-pixel/method-4 candidate increased upload CPU; it was replaced by the measured 512-pixel/method-0 variant. Alpha values remain preserved. A corrupt PNG checksum was also found to escape the raw validator as `SyntaxError`; it now becomes the normal validation error, with a regression test.

Targeted non-avatar model saves previously issued an unnecessary avatar lookup. Moving the existing `update_fields` guard before that lookup reduced a measured profile-name save from **two queries to one**, with unchanged file cleanup behavior and a query-count test.

## Frontend and extended API review

Controlled direct dashboard navigation made **four** identical workspace metadata requests before, and **one** after in-flight sharing. Keys include both token and workspace; entries disappear on success or failure. No result, JWT or permission cache is retained. Unit tests check isolation and fresh subsequent requests; Playwright asserts the observed one-request result.

`benchmark_reads --tasks 10000 --projects 10 --repeats 5 --explain --extended` additionally creates 100 temporary comments/messages/notifications and three private reminders, all rolled back:

| Endpoint | Median ms | Queries |
| --- | ---: | ---: |
| Task list | 15.56 | 4 |
| Dashboard, existing complete API response | 67.54 | 16 |
| Comments | 16.97 | 6 |
| Chat messages | 19.96 | 8 |
| Chat unread | 9.97 | 3 |
| Notifications | 20.81 | 2 |
| Notification unread count | 9.24 | 1 |

No individual SELECT exceeded the benchmark's 50 ms plan threshold. These owner-scoped fixtures are not a replacement for production concurrency monitoring. No response cache, new Redis keys, index changes or worker concurrency changes were justified. The bundle inventory was 42 build chunks, 1,024,361 raw bytes / 324,255 gzip bytes across **all routes**, not one page. Browser tests print a lab-only landing LCP/CLS/navigation snapshot; no field INP or production p75 claim is made, and no user tracking was added.

The shared browser fixture server now lives at `config/tests/browser_server.py`; Playwright invokes the updated path. Test output remains inside ignored `artifacts/`, `client/test-results/` and `client/playwright-report/`.

Final verification: 970 backend tests and 182 subtests passed in 100.37 seconds with real Redis enabled; 66 frontend tests and all eight desktop/mobile browser scenarios passed. Django checks, migration drift check, OpenAPI validation and Compose validation passed. The final local landing snapshot recorded LCP 268 ms, CLS 0 and 157,273 transferred JavaScript bytes; this single local lab run is not a before/after or field performance claim.
