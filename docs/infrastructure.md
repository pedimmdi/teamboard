# Redis, Celery and selective caching

## Runtime contract

PostgreSQL remains authoritative for accounts, sessions/JWT blacklists, memberships, permissions, messages, tasks, notifications, and durable background work. No API-wide caching or permission caching is enabled. Redis database 0 is the Channels transport, database 1 is shared DRF throttle history, and database 2 is the Celery broker. Database numbers do not isolate resource usage or availability. Deploy independent Redis instances when workload/resource isolation is required. Use environment-specific `CACHE_KEY_PREFIX` values if deployments share a cache, and separate `CHANNEL_REDIS_PREFIX` values for Channels. Isolate broker databases/instances across environments as well.

The Redis image is pinned to a verified official 7.4.10 digest. Local port exposure is loopback-only; the production overlay removes it. Configure ACL/password and TLS on externally hosted Redis using `rediss://` URLs; never put credentials in source control. Celery verifies TLS certificates. Do not disable certificate validation. The local Compose stack is a development environment; public production traffic requires an external TLS reverse proxy and production Django settings.

AOF uses every-second fsync and `noeviction`. A host/power failure can lose the most recent Redis writes; this is not a durable business-data store or an HA deployment. The PostgreSQL outbox recovers lost broker messages. Channels is transient: clients retain their existing database synchronization/reconnect behavior. Cache/throttle failures are visible rather than silently allowing requests. Existing DRF rate limits are approximate under concurrent requests, not strict distributed quotas.

## Transactional outbox and guarantees

`background.BackgroundJob` is created in the same database transaction as the related registration, invitation, or attachment deletion. Only its UUID is sent to Celery after commit. Rollback removes both the job and the commit callback. A broker outage does not fall back to synchronous SMTP or storage work; a pending database row survives and recovery republishes it.

Worker execution locks the job row. Duplicate/concurrent deliveries skip terminal work. SMTP and storage timeouts/errors receive bounded exponential retry (30 seconds initially, up to one hour); transient SMTP 4xx responses retry and permanent 5xx responses fail. The durable attempt budget is eight, bounded additionally by job expiry. Worker late acknowledgement, reject-on-worker-loss, visibility timeout, prefetch=1, and hard/soft limits protect long-running work. A dispatch lease prevents recovery from flooding the broker while a worker is offline; a lost accepted delivery is recoverable after ten minutes. Recovery runs every 30 seconds in batches of at most 100.

SMTP cannot promise exactly-once delivery: a process can die after a mail server accepts an email but before PostgreSQL records completion. Each job uses a stable Message-ID to help provider deduplication, but only a provider with an idempotency API can close that gap. Do not describe this as guaranteed exactly-once email. Correct permanent mail failures and request a new resend through the application; terminal payloads are deliberately not retained for replay. File deletion is idempotent: an already absent file is safe; chat deletion additionally rechecks that the attachment belongs to a soft-deleted message. Comment cleanup rechecks that no attachment row references its key.

Email payloads (including verification/invitation URLs) are temporary private PostgreSQL outbox data, not Redis/cache data. They expire after one hour and are erased on terminal processing or the next expiry sweep. Verified/deactivated accounts, invalid password-reset tokens, rotated/accepted/revoked invitations, and deleted invitation records are rechecked before sending. Terminal metadata is retained for seven days. Cleanup jobs expire after seven days. Logs contain job IDs, kinds, error classes and attempts, not email bodies/tokens or broker credentials. The development console email backend intentionally prints emails; use a real SMTP backend in production.

Only one Beat instance should run. If Redis is unavailable, Beat cannot enqueue its recovery task. Run `python manage.py recover_background_jobs` from an external scheduler as well when strict payload-retention or outage-recovery requirements apply: it performs the expiry sweep directly, independently of broker availability. Do not add automatic live orphan-file deletion: existing conservative cleanup commands retain their 24-hour grace, reference checks and documented maintenance/write-pause requirements.

## Deployment

Required processes: PostgreSQL, Redis, ASGI backend, Celery Worker and one Celery Beat. The worker and backend must share the same private attachment storage and matching access permissions. Default image UID/GID is 10001. The image excludes all private uploads and local logs/build/test artifacts.

For the backend production overlay (Compose 2.24.4+), create the private `.env` first. To use another environment file, set `APP_ENV_FILE` and pass that same file with `--env-file`; CI validates with the committed `.env.example` rather than relying on a private `.env`:

```sh
docker compose -f docker-compose.yml -f docker-compose.production.yml build backend worker beat
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.production.yml run --rm --no-deps backend python manage.py migrate --noinput
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d backend worker beat
```

This overlay provides Daphne, immutable source, read-only root filesystems, temporary writable `/tmp`, private named storage volumes, no public Redis/backend ports and a Redis memory budget. Attach an external reverse proxy to the application network; frontend production hosting is separate. For multiple backend instances use the proxy for routing to their internal port 8000. Do not use development `runserver` for public production traffic.

Set a strong `SECRET_KEY`, `DEBUG=False`, correct `ALLOWED_HOSTS`, origins, HTTPS/proxy/cookie security settings and an SMTP backend. SMTP environment settings include `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` or `EMAIL_USE_SSL`, and `EMAIL_TIMEOUT` (15 seconds). Never enable both TLS and SSL simultaneously. Back up PostgreSQL and all three media/private storage volumes together; new named volumes do not automatically migrate development uploads. Existing deployments with custom storage roots must adapt volume mounts accordingly.

Health checks cover Redis readiness, the backend listening after development migrations, and the individual Celery worker control endpoint. They are liveness/readiness aids, not end-to-end delivery guarantees. Monitor pending count/oldest age, failed jobs, worker/Beat availability, broker memory/disk and Redis eviction/error metrics. A successful health ping alone does not prove SMTP delivery. Alert on any terminal failures and unusual backlog growth; inspect only sanitized outbox metadata.

## Verification and recovery

```sh
RUN_REDIS_TESTS=1 python -m pytest -q
celery -A config inspect ping
python manage.py recover_background_jobs
python manage.py background_status --max-pending-age 600
python manage.py cleanup_chat_attachments --help
python manage.py cleanup_orphan_attachments --help
```

Real integration tests use UUID-prefixed Redis keys/queues and a separate Celery process against the test database, with file-based mail instead of external SMTP. They verify cross-process Channels delivery, shared throttles/cache, fail-closed cache outages, commit timing, duplicate workers/deliveries, durable retry/expiry and attachment cleanup. No shared Redis database is flushed. Unit tests explicitly isolate transport/cache and use eager Celery; application execution never silently selects those test backends.

## Read benchmarks and cache decision

`python manage.py benchmark_reads --tasks 10000 --projects 10 --repeats 5 --explain` creates disposable fixtures in a transaction, benchmarks actual authorized endpoints and rolls fixture rows back. Run only on a development/staging or disposable database: it consumes sequence values, creates temporary load, and refreshes planner statistics. Statistics are refreshed for synthetic rows before measurement and the real dataset afterwards; otherwise a tiny database's stale estimates can misleadingly produce quadratic nested-loop plans. `EXPLAIN ANALYZE` is read-only and includes only generated fixtures.

Local PostgreSQL 17 / Docker Desktop, 10 projects, 10000 tasks, five repetitions, no application cache:

| Endpoint | Median ms | SQL queries |
| --- | ---: | ---: |
| Projects | 7.01 | 4 |
| 90-day historical reports | 29.73 | 8 |
| Workload | 8.74 | 2 |
| Project ranking | 28.11 | 3 |
| 7-day calendar timeline | 23.92 | 4 |

These are local diagnostic results, not a production latency SLA or proof of unlimited scale. APIClient uses forced authentication to isolate application reads; live permission checks still run, but network/proxy/JWT validation costs and load-test concurrency are excluded. An initial un-analyzed fixture produced a multi-second historical query; EXPLAIN identified stale row estimates, and representative statistics removed that plan without changing application queries. No cache for reports, calendars, projects, or counters is justified by the measured results, so none is enabled. Existing indexed queries and permission checks remain unchanged. Re-run with representative production distributions/concurrency before introducing any report cache. A future cache must recheck live access before every hit, include user/workspace/project/filter and permission scope in its key, define a short TTL plus committed-write invalidation, and demonstrate rollback/revocation safety before activation.

References: [Celery task reliability](https://docs.celeryq.dev/en/stable/userguide/tasks.html), [Channels production layers](https://channels.readthedocs.io/en/stable/topics/channel_layers.html), [Django cache backends](https://docs.djangoproject.com/en/5.2/topics/cache/).
