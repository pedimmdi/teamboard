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
