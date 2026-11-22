# Measured performance review

Measurements: local Docker Desktop / PostgreSQL 17, November 2026. Raw logs and JSON are kept locally in ignored `artifacts/`, never in the repository. Values are observations, not production SLAs. Read benchmarks use disposable fixtures with rollback and representative planner statistics.

## Baseline and decisions

`docker compose exec backend python manage.py benchmark_reads --tasks 10000 --projects 10 --repeats 5 --explain`

| Authorized endpoint | Median ms | Queries |
| --- | ---: | ---: |
| Projects | 7.42 | 4 |
| Historical reports, 90 days | 32.49 | 8 |
| Workload | 8.94 | 2 |
| Project comparison | 28.68 | 3 |
| Calendar, seven days | 28.82 | 4 |

No slow plans were found in these measurements. Existing query-count regression tests remain enabled. There is no evidence here for another index, response cache, permission cache or query rewrite. No such changes were made.

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
