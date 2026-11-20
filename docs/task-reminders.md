# Task reminders

Reminders belong to `tasks`; in-app delivery belongs to `notifications`. The existing worker and single Beat instance are used. No separate app, scheduler, cache, email or push channel is introduced. Run normal migrations and restart worker/Beat when deploying this feature.

## API and privacy

Base path: `/api/v1/workspaces/<slug>/projects/<project_id>/tasks/<task_id>/reminders/`.

- `GET` lists only the authenticated user's reminders, 20 per page, active states first. Historical sent/cancelled rows remain available.
- `POST` creates a reminder. Absolute example: `{"kind":"absolute","timezone":"Asia/Tehran","run_at":"2030-05-20T05:30:00Z"}`.
- Relative example: `{"kind":"relative","timezone":"Asia/Tehran","days_before":1,"local_time":"09:00"}`. Omitted relative settings default to zero days and 09:00.
- `PATCH <reminder_id>/` edits an unsent reminder. Switching to absolute requires `run_at`; switching to relative defaults missing relative settings. Unknown fields, including recipient/user/task/status controls, are rejected.
- `DELETE <reminder_id>/` cancels an unsent reminder idempotently. Delivered rows retain their delivery audit; manage the delivered notification normally through the inbox.

Workspace Owners/Admins and Project Managers/Members with task access may schedule reminders for themselves. Privileged roles cannot inspect or manage another user's reminders. Cross-workspace/project/task paths and foreign reminder IDs do not expose private data. Read/write throttles are 120/30 requests per minute per authenticated user, using the existing shared throttle cache.

At most three active rows (pending, disabled, invalid, failed) are allowed per user/task. Concurrent API writes serialize through the project's existing workspace-first lock. Cancel a row to release its slot. Duplicate active timestamps, past times and completed tasks are rejected. A database partial unique constraint also guards duplicate pending timestamps.

## Time and due-date behavior

PostgreSQL stores aware instants; API output uses UTC. Each reminder stores its chosen IANA timezone, separately from the user's browser timezone. The drawer initially suggests the browser timezone and allows changing it. Absolute input is interpreted in that selected zone; changing the zone keeps the entered wall-clock value. The exact time and zone are displayed in the list.

Absolute reminders retain their instant when the task's due date changes or is removed. Relative reminders derive their instant from `due_date - days_before` at `local_time` in the selected zone. A date-only due date has no inferred deadline hour, so no “one hour before deadline” preset is offered. Days-before is bounded to 0–365. Ambiguous/nonexistent local DST times are rejected rather than silently shifted; choose another time (API absolute timestamps may specify an explicit offset).

The database task-update trigger marks unsent relative reminders for recalculation, including bulk/SQL updates. The service update path recalculates immediately in its transaction. Listing reminders and the periodic worker reconcile remaining dirty rows. Removing the due date disables relative reminders; restoring a future due date reactivates them. A changed due date yielding a past instant, invalid DST time, or duplicate pending timestamp marks the reminder invalid for explicit rescheduling. An unchanged instant that became overdue during an outage still delivers. Completion cancels active reminders; reopening does not recreate them.

## Delivery, failure and concurrency

Beat dispatches `tasks.reminder_jobs.dispatch_due_reminders` every 60 seconds. The worker selects at most 100 due/retry/dirty rows per invocation using partial schedule indexes, then processes each in a separate database transaction. Multiple workers/overlapping scans may select the same IDs; workspace/project/task/reminder locks serialize the actual delivery. A second live access check includes active account, workspace membership and project access before creating the notification. Reassignment alone does not cancel reminders belonging to other authorized project members. Task/user deletion cascades reminder rows.

Notification creation and the reminder's `sent` status, timestamp and notification reference commit atomically. Stable `task_reminder:<reminder_uuid>` deduplication keys prevent duplicate notifications even on redelivery. The TASK_REMINDER event uses normal task/project scopes and the existing inbox access filtering, unread count, read management and direct task link.

States:

| State | Behavior |
| --- | --- |
| pending | Wait for its instant, then deliver |
| disabled | Due date removed; wait for a new due date or user edit |
| invalid | Recalculation needs a new valid future time; editable/cancellable |
| failed | Transaction rolled back; retry automatically with exponential delay capped at one hour; editable/cancellable |
| sent | Terminal delivery audit, with notification reference and timestamp |
| cancelled | Terminal; completion, revoked access or explicit cancellation |

An unexpected processing exception rolls back notification and delivery state together. A separate transaction records only the exception class and retry time; no message content, email or task title is logged. Failed reminders keep retrying with bounded frequency, so alert on persistent failures. If the database is unavailable even for recording failure, the transaction remains uncommitted and the next Beat scan recovers the original pending row. Worker termination behaves the same way. Redis outage/lost broker delivery cannot lose the PostgreSQL schedule: after recovery, the next successful periodic scan finds overdue reminders. No long-term Redis ETA jobs are used, and no user/permission/reminder data is cached.

The 60-second interval is a polling target, not an exact delivery SLA. A backlog larger than 100 eligible rows drains across scans; monitor delay and increase worker/scan capacity only after measuring lock contention. Existing workspace-first locks favor correctness and may serialize busy workspaces.

## Operations and tests

```sh
docker compose exec backend python manage.py reminder_status --max-overdue-age 300
docker compose exec backend celery -A config inspect registered
docker compose logs worker beat
```

`reminder_status` returns counts, oldest pending due age, due retries and dirty rows without identifiers or private content. Monitor failed rows and retry backlog as well as oldest pending age. Restore PostgreSQL/Redis/worker/Beat availability first; the periodic job recovers automatically. For a controlled manual drain, run `docker compose exec backend python manage.py shell -c "from tasks.reminders import scan_due_reminders; scan_due_reminders()"`. Do not reset sent rows or delete deduplication records to retry delivery.

Backend tests cover private CRUD, roles/revocation, limits and concurrent creates, UTC/IANA/DST, due-date bulk changes, task completion/deletion, reassignment, delayed execution, atomic rollback/retry, duplicate workers, database constraints and throttles. A real Redis/separate-worker test exercises publication failure, worker restart and duplicate periodic dispatch. Run integration tests with `RUN_REDIS_TESTS=1`. Frontend unit tests cover UTC conversion and API contracts; Playwright exercises error recovery, fixed and relative CRUD, due-date changes, mobile layout and inbox deep links. Existing test suites remain enabled.
