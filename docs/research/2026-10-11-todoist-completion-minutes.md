# Todoist completed-task data for deep-block minute logging

Wayfinder ticket #8 (part of #6). Date: 2026-10-11. Sources are Todoist's primary docs only:
the unified API v1 reference at https://developer.todoist.com/api/v1/ (rendered from
https://developer.todoist.com/openapi.json, which is what the quotes below come from) and
Doist's own Python SDK (github.com/Doist/todoist-api-python). No live API call was made.

Local code read: `src/todoist.py` (`TodoistCompletionClient`), `src/streaks.py`, `src/xp.py`,
the sweep in `src/main.py`, `STATUS.md` ("live-probe" notes), `.github/workflows/daily.yml`.

## 1. The endpoint: `GET /api/v1/tasks/completed/by_completion_date`

Source: `openapi.json` → `paths["/api/v1/tasks/completed/by_completion_date"]`, anchor
https://developer.todoist.com/api/v1/#tag/Tasks/operation/tasks_completed_by_completion_date_api_v1_tasks_completed_by_completion_date_get

- Description (verbatim): "Retrieves a list of completed tasks strictly limited by the specified
  completion date range (up to 3 months)." "By default, the response is limited to a page containing
  a maximum of 50 items (configurable using `limit`). Subsequent pages of results can be fetched by
  using the `next_cursor` value from the response as the `cursor` value for the next request."
- Parameters:
  - `since` (required, `date-time`): "Start of the completion date range, inclusive." Example `2025-02-01T00:00:00Z`.
  - `until` (required, `date-time`): "End of the completion date range, **exclusive**." Example `2025-02-28T23:59:59Z`.
  - `project_id` (string, optional): "Project ID to limit completed tasks to." Also `workspace_id`,
    `section_id`, `parent_id`, `filter_query` (Todoist filter syntax), `filter_lang`.
  - `cursor`: opaque, "Must be used with the same parameters from the previous request".
  - `limit` (integer, default 50): "Maximum number of completed tasks to return." The operation
    schema states no maximum; the general Pagination guide
    (https://developer.todoist.com/api/v1/#tag/Pagination) says "Default: 50, Maximum: 200 ... If you
    specify a limit greater than 200, the API will return a validation error", and the Doist SDK
    constrains `limit` to 1..200. The engine's `COMPLETION_PAGE_LIMIT = 200` is at the ceiling.
- Max span: "up to 3 months" is the only statement. Not defined in days. The engine's 90-day window
  is at or just under that; a Dec→Feb 90-day window could exceed "3 calendar months" by a day.
  Ambiguous in the docs; for minute logging only the last 1-2 days are needed anyway.
- Response schema `TasksCompletedDateResponse`: `items` ("Completed tasks in the current page.")
  and `next_cursor` ("Cursor for the next page ... Omitted when there is no next page."). Note the
  key is `items`, not the `results` key the generic Pagination guide shows; this matches the
  2026-05-04 live probe recorded in `STATUS.md`.
- Each item is a full `ItemSyncView` (same shape as a Sync-API task; no separate `item_object`
  wrapper, `item_object` does not appear anywhere in the v1 spec). Fields relevant here:
  `id` ("String ID of the task."), `project_id`, `section_id`, `parent_id`, `content`,
  `description`, `labels`, `checked` ("Whether the task is completed."), `completed_at`
  ("Date and time when the task was completed, or `null` if active."), `completed_by_uid`,
  `added_at`, `updated_at`, `due` ("Due date details for the task, or `null` when the task has no
  due date."), `deadline`, `duration` ("Task duration details, or `null`"), `priority`,
  `completed_count` ("Number of times the task has been marked as completed ..."), `postponed_count`.
- Sibling endpoint `by_due_date`: same params, "(up to 6 weeks)", windowed on the due date instead.
- Migration table (https://developer.todoist.com/api/v1/#tag/Migrating-from-v9): `/sync/v9/completed/get_all`,
  `/sync/v9/archive/items` and `/sync/v9/archive/items_many` are all replaced by
  `/api/v1/tasks/completed/by_completion_date`. So this is the right endpoint, with no alternative
  bulk completed-tasks read.
- Doist SDK (`todoist_api_python/api.py`, `_core/endpoints.py`): `get_completed_tasks_by_completion_date`
  hits `tasks/completed/by_completion_date`, docstring "up to 3 months", "default 50", reads `items`
  and follows `next_cursor`. (The SDK method exposes no `project_id` kwarg; the spec does. Spec wins;
  the engine already passes `project_id`.)

## 2. Timezone of `completed_at`; attributing to an Asia/Kolkata date

- The `ItemSyncView.completed_at` schema says only `format: date-time`. It does not name a zone.
- Evidence it is UTC with a `Z` suffix:
  - Sync command `item_complete`, arg `date_completed`: "RFC3339-formatted date of completion of
    the task (in UTC). If not set, or more than 24 hours in the future, the server will set the
    value to the current timestamp." (https://developer.todoist.com/api/v1/#tag/Sync/Tasks/Complete-item)
  - Sync task examples show `"added_at": "2025-01-21T21:28:43.841504Z"`, `"updated_at": "...Z"`.
  - Doist SDK `models.py` types `completed_at: Optional[ApiDate]` with
    `ApiDate = UTCDateTimePattern["%FT%T.%fZ"]`, i.e. it parses a UTC, fractional-second, `Z` string.
  - The request examples for `since`/`until` are `...Z`.
- Verdict: treat `completed_at` as UTC (RFC 3339, `Z`, microseconds). Attribution:
  `datetime.fromisoformat(completed_at.replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Kolkata")).date()`.
  Python 3.11+ `fromisoformat` accepts the `Z` directly. State a 1-line assumption in the code and
  confirm with the existing read-only `scripts/probe_completion.py` (it prints the raw JSON) when
  the token is next used; the probe already exists, so no new tooling.
- `since`/`until` should be sent as UTC instants covering the IST day: for IST date D,
  `since = D 00:00 IST = (D-1) 18:30Z`, `until = (D+1) 00:00 IST` (exclusive bound, per the spec).

## 3. Late completions and the original due date

- `completed_at` is the real completion instant, server-set at completion time (see `item_complete`
  above), so a block done Saturday 11:00 IST vs Sunday 07:00 IST yields different IST dates. Late
  completion is distinguishable from the API data.
- The completed item carries `due` (object or null). The spec does not say explicitly whether `due`
  is preserved on a completed non-recurring task, only that it is "null when the task has no due
  date". Ambiguous; do not depend on it.
- Not needed anyway: the engine's own create cache already stores `due_date` and `template_id` per
  `todoist_task_id` (`src/todoist.py` `cache[external_id] = {todoist_task_id, created_at,
  template_id, due_date}`), so the intended block date comes from the local join, and "late" is
  simply `ist_date(completed_at) != cache.due_date`. The attribution rule (log on completion date vs
  on due date) is a spec-level decision for #6; both inputs are available.
- The engine creates one task per date, never recurring tasks, so `completed_count` and recurring
  `due` semantics do not apply.

## 4. Rate limits for one GET per run

- The v1 "Request limits" section (https://developer.todoist.com/api/v1/#tag/Request-limits) states
  only: 1 MiB POST body, 65 KiB headers, 15 s standard-request timeout, and Sync limits "maximum of
  1000 partial sync requests within a 15 minute period" / "100 full sync requests within a 15 minute
  period" per user. It states no per-endpoint quota for `/tasks/*` GETs. 429 is documented generically
  ("The user has sent too many requests in a given amount of time."), and errors may carry
  `retry_after` ("Seconds to wait before retrying. May be returned on rate-limited requests and other
  API errors, not just `429` responses.").
- One GET per daily run (plus up to a few cursor pages) is orders of magnitude below any of these.
  The REST v2 page now redirects to the v1 reference, so the old v2 "450 requests per 15 minutes"
  figure is no longer a primary-source claim. The client's retry loop does not honour `retry_after`
  or treat 429 specially (it raises on any non-5xx non-OK); irrelevant at this volume.

## 5. Id stability and joining with the create cache

- Migration guide, "IDs": "Since 2023, our objects returned `v2_*_id` attributes. That 'v2 id' has
  now become the main `id`. ... This version officially makes them non-number opaque strings". Old
  numeric ids are rejected for tasks. `/api/v1/id_mappings/{obj_name}/{obj_ids}` translates between
  the two generations (up to 100 ids).
- `ItemSyncView.id` is "String ID of the task", the same `id` returned by `POST /api/v1/tasks`
  (which the engine stores as `todoist_task_id`). Both are v1 ids; the engine never used the old
  API, so no mapping is needed. Nothing in the docs says a task's id changes on completion, and the
  live probe (STATUS.md, 2026-05-04) confirmed the per-item key is `id` and the sweep already joins
  successfully on it. Caveat: `dict[str,...]` keys must stay strings (the client already `str()`s them).

## What the existing client + cache already provide

- `TodoistCompletionClient._fetch_completed_ids` (src/todoist.py) hits the right endpoint with
  `since/until/limit=200/project_id` and follows `next_cursor`; response shape (`items`, `id`) is
  locked against the live probe.
- Create cache (`.cache.json` per syllabus, via `src/cache.py`): `external_id -> {todoist_task_id,
  template_id, due_date, created_at}`. Deep-block tasks are identifiable by `template_id`
  (and label `deep-block` on the template; `src/main.py` already maps that to kind `deep_block`).
- Daily sweep (`src/main.py` ~L1240-1300): for entries with `due_date < today` and no status, asks
  `get_completion_status` and sets `status="completed"`, `completed_at=today.isoformat()`.
- `.completion_cache.json`: `{fetched_at, completed_ids: [...], project_id}`, 6 h TTL.
- Timezone plumbing: `Clock(state.timezone)` / `tz_name` already exist in `src/main.py`.
- Cron: `daily.yml` runs at `30 21 * * *` UTC = 03:00 IST (the ticket says ~06:00; the workflow
  comment says 03:00). Either way it is after the previous IST day closed.

## What is missing for per-date minute logging

1. **The completion timestamp is thrown away.** `_fetch_completed_ids` keeps only `item["id"]`;
   `completed_at` (and `content`, `project_id`) are dropped. Needs to return `dict[id -> completed_at]`
   (one dict instead of a set), and `.completion_cache.json` needs `completed: {id: completed_at}`
   instead of `completed_ids: [...]` (old files fail the shape check and are refetched; no migration).
2. **The sweep's `completed_at` is the run date, not the completion date.** `cache[ext]["completed_at"]
   = today_iso` labels every completion with the morning the sweep noticed it, so a Saturday block
   is stamped Sunday. Once (1) exists, write the API value (converted to IST date) instead.
3. **IST conversion** of `completed_at` (UTC) -> `date` as in section 2. No code does this yet.
4. **Minutes have no source in Todoist data.** Created tasks carry no `duration` object (the
   deep-block template only says "3-4 hr" in prose), and the API's `duration` field would be null.
   Minutes must come from the engine side: the per-weekday deep-block window in `seasons.yaml`
   rhythm (#6 decision), keyed by the block's `due_date` weekday. Setting `duration` on create is
   possible (`{"amount": N, "unit": "minute"}`, Sync "Tasks" properties) but duplicates the YAML.
5. **The 6 h TTL can hide a completion** only if a manual `workflow_dispatch` ran within 6 h before
   the cron; the cron-only path always refetches. Acceptable; or bypass the cache for the
   minute-logging fetch, which only needs a 1-2 day window.
6. **Window**: 90 days sits at the documented "up to 3 months" edge. For minute logging use a short
   window (yesterday 00:00 IST -> now) rather than widening anything.

Ambiguities to carry into the spec: `completed_at` zone is UTC by all evidence but not stated on the
schema; the `limit` max (200) comes from the generic guide, not this operation; "3 months" is not
defined in days; `due` persistence on completed items is unstated.
