# STATUS

Phases A and B complete. Production daily run validated end-to-end (cron + workflow_dispatch). All 136 tests passing locally and in CI.

## Phase A — walking skeleton + CLI retrofit *(2026-05-04)*

End-to-end happy path: two daily Todoist tasks created from templates, idempotent across reruns, tested with mocked HTTP, scheduled via GitHub Actions cron.

### Amendment to the original "write-only Phase A" constraint

**Original wording (PROMPT.md / SPEC.md):** *"Strict read/write separation in todoist.py. Phase A is write-only on Todoist."*

**Amended interpretation:** the daily-run client is **write-only on TASK STATE** (no PATCH, no DELETE, no POST outside `create_task_idempotent`). **Idempotency reads are permitted**: a single GET to list project tasks and parse content markers, fired lazily on the first cache miss and memoized for the rest of the run. Without this, the spec's "two-layer dedup" was a half-feature: the marker is written but never read until Phase F's `rebuild_cache.py`, which means a deleted/corrupt cache file would silently duplicate tasks. The amendment makes the marker layer load-bearing at runtime.

The Phase E completion API (`get_completion_status`) is still strictly separate — must not share a retry wrapper, helper, or session-scoped state with `create_task_idempotent`.

Destructive operations (DELETE) live on a *separate class* `TodoistAdminClient` invoked only by the `--cleanup-project` CLI subcommand.

## Phase B — all ritual cadences *(2026-05-04)*

Cadence dispatch in the scheduler (`paused`, `daily`, `weekly`, `monthly`, `quarterly`, `annual`), plus the matching ritual templates parsed from the syllabus.

## What works

### Code
- `src/ids.py` — deterministic SHA256-based `external_id(template_id, due_date)`. Includes `module_external_id(template_id, module_number)` shape for Phase D.
- `src/cache.py` — JSON cache load/save with atomic write, corruption tolerance, 60-day pruning. `prune` requires `now=` (no system-clock fallback) to enforce the single injection point.
- `src/clock.py` — single injection point for the system clock. `Clock(tz)` for production, `FrozenClock(when, tz)` for tests and `--today`. `grep -rn "datetime\.now\|date\.today\|time\.time" src/` returns exactly one line.
- `src/config.py` — loads `config.yaml` and the Todoist token from `.env` (10-line stdlib parser) or `TODOIST_TOKEN` env var. `Config.__repr__` redacts the token; `TokenRedactingFilter` strips it from any log record.
- `src/state.py` — loads and validates `state.yaml`. Required keys, ZoneInfo, date checking. Dataclass scaffolds Phase D–F fields (`completed_modules`, `manual_counters`, etc.).
- `src/templates.py` — loads `task_templates/*.yaml` and resolves `{current_book}` and `{ritual_times.<key>}` placeholders. **Phase B**: parses `day_of_week` and `day_of_month` (int or string `last-day` / `last-saturday`) into the `Template` dataclass; unknown YAML fields stay in `template.raw` for forward-compat (Phase C reads `reflection.create_stub` from there).
- `src/scheduler.py` — **Phase B cadence dispatch** with `paused` short-circuit at the top:
  - `paused: true` → False for every cadence (including `once-per-module`, so future Phase D drift doesn't crash a paused run).
  - `daily` — `skip_if=sunday` + `config.sunday_off` + Sunday → False; else True.
  - `weekly` — `today.weekday()` matches `template.day_of_week` (calendar-based, not ISO-week-based; verified for 2027-01-01 / ISO W53 of 2026 boundary).
  - `monthly` — `template.day_of_month` is int 1–28 (refuses 29/30/31), or `last-day`, or `last-saturday`. Anything else raises NotImplementedError naming both the rule and the template id.
  - `quarterly` — Jan 1 / Apr 1 / Jul 1 / Oct 1, regardless of weekday.
  - `annual` — Jan 1.
  - `once-per-module` and other unknown cadences raise NotImplementedError; Phase D wires them.
  - **2029-04-01 (Sun + Q2 boundary) regression test**: quarterly fires, daily-with-sunday-skip does not. Same `should_create_today` call, two templates, opposite answers.
- `src/todoist.py` — `TodoistClient.create_task_idempotent`. Cache hit = zero API calls; cache miss = up to one GET (memoized) for marker dedup, then if still novel, one POST with `<!--LW:{id}-->` appended to description. Marker hit *rehydrates the in-memory cache* so the next run hits the fast path. Retries 3× on 5xx with exponential backoff, raises immediately on 401, raises on other 4xx without retry. Endpoint base: `https://api.todoist.com/api/v1` (REST v2 deprecated 2026-05-04). Module docstring + regression test enforce no PATCH/DELETE methods on the daily-run client. Destructive ops live on `TodoistAdminClient` (used only by `--cleanup-project`).
- `src/main.py` — orchestrates one run: load config + state + templates → today in owner TZ → for each template `should_create_today`? → resolve variables → check cache → check marker layer (lazy) → create → update cache → prune → save → append `LOG.md`. CLI: `--dry-run`, `--today YYYY-MM-DD`, `--project-id`, `--cache-file`, `--verbose`, `--cleanup-project ID [--yes]`. **Phase B**: `_classify_skip` extended for paused (highest precedence) and per-cadence reasons (`SKIP (paused)`, `SKIP (Sunday)`, `SKIP (not friday)`, `SKIP (not month boundary)`, `SKIP (not quarter boundary)`, `SKIP (not Jan 1)`).

### Configuration
- `state.yaml` — `start_date: 2026-05-04`, timezone `Asia/Kolkata`, `current_book` set to "Computer Systems: A Programmer's Perspective" (hardcoded; Phase D replaces with parser).
- `config.yaml` — real Todoist project ID `6gWxC2wh5WRvjfw2`, real github_username `SauravSuresh`, all five ritual times, full label set including `annual: annual-ritual`.
- `.env.example` — `TODOIST_TOKEN=` placeholder. Real `.env` is gitignored; `TODOIST_TOKEN` also lives as a GitHub repo secret.

### Templates *(10 active)*
- `task_templates/daily.yaml` — `daily-morning-reading`, `daily-anki`, `daily-evening-hands-on`. All `cadence: daily`, `skip_if: sunday`.
- `task_templates/weekly.yaml` — `weekly-friday-review` (Friday, with reflection stub for Phase C), `weekly-saturday-deep-block` (Saturday).
- `task_templates/monthly.yaml` — `monthly-blog-post` (day 1), `monthly-retrieval` (last Saturday, with reflection stub), `monthly-review` (last Saturday, chained after retrieval).
- `task_templates/quarterly.yaml` — `quarterly-synthesis` (with reflection stub).
- `task_templates/annual.yaml` — `annual-review` (with reflection stub).

### Tests *(136 passing, all stdlib + mocked HTTP)*
- `tests/test_ids.py` — determinism, distinctness, hex shape (5 tests).
- `tests/test_cache.py` — round-trip, missing/corrupt handling, prune (7).
- `tests/test_clock.py` — Clock + FrozenClock, owner-TZ day boundaries (6).
- `tests/test_config.py` — `.env` parser, env-var fallback, missing-token, redaction (9).
- `tests/test_state.py` — happy path, malformed-input exits (4).
- `tests/test_templates.py` — load directory, resolve `{current_book}`/`{ritual_times.X}`, missing variable returns None, **`day_of_week` and `day_of_month` parsing, reflection block survives in raw** (8).
- `tests/test_scheduler.py` — **48 tests** covering paused-blocks-each-cadence, daily Sunday skip, weekly day-of-week (incl. ISO week boundary), monthly int / last-day / last-saturday, quarterly all four boundaries, annual, **2029-04-01 edge case**, unknown cadence + value error messages, helper functions.
- `tests/test_todoist.py` — marker format, cache hit = 0 calls, cache miss = 1 POST, marker dedup skips/creates, **5 cache misses → 1 GET (memoization)**, paginated marker fetch, marker hit rehydrates cache, dry-run skips POST, clock-driven `created_at`, admin list/delete, no destructive methods on `TodoistClient`, token never logged (24).
- `tests/test_main.py` — end-to-end with FakeClient: Monday creates, second-run cache hits, Sunday creates 0, LOG.md appends (4).
- `tests/test_main_cli.py` — argparse, `--dry-run`, `--today`, `--project-id`, `--cache-file`, `--cleanup-project [--yes]`, **paused dry-run all SKIP (paused), paused real-run still writes cache + log** (21).

### CI / scheduling
- `.github/workflows/test.yml` — runs `pytest -q` on PRs and pushes to main, Python 3.11.
- `.github/workflows/daily.yml` — `cron: "30 21 * * *"` (03:00 next-day Asia/Kolkata) + `workflow_dispatch`. Permissions `contents: write`. Reads `secrets.TODOIST_TOKEN`. Commits `.task_cache.json` and `LOG.md` if changed, pushes. Concurrency group `daily-run`.

## What is stubbed / deliberately deferred

- **Reflection stubs.** Phase B's templates carry `reflection.create_stub: true` and `stub_path` strings as inert YAML data. Phase C wires `src/reflections.py` and the path resolver (`{iso_year}-W{iso_week:02d}`, `{year}-{month:02d}`, `{year}-Q{quarter}`, `{year}`).
- **Completion API (`get_completion_status`).** Phase E. Marker-dedup reads exist but list active tasks for a project — different endpoint, different concern.
- **Module / once-per-module cadence.** `module_external_id` exists in `src/ids.py`; scheduler raises NotImplementedError. Phase D wires it.
- **Syllabus parser.** `current_book` is hardcoded in `state.yaml`. Phase D adds `src/syllabus.py`.
- **Dashboard.** No `docs/`, no `src/dashboard.py`, no `data.json`. Phase E.
- **`rebuild_cache.py` (Phase F).** Runtime marker dedup handles the common case of cache loss; Phase F's offline script handles the long tail (older days outside the prune window, completed tasks).
- **`dry_run` workflow input.** Local CLI has `--dry-run` (Phase A retrofit). Surfacing it as a `workflow_dispatch` input is a Phase F task.

## UX flags worth tracking

- **Last-Saturday triple-firing.** On the last Saturday of any month, three Saturday-time tasks fire simultaneously: `weekly-saturday-deep-block` + `monthly-retrieval` + `monthly-review`. This is intentional per the syllabus (deep block continues happening; retrieval and review are monthly cadences that landed on the same Saturday). Owner may eventually want `weekly-saturday-deep-block` to skip on last-Saturdays so the monthly tasks subsume it. Not a Phase B fix — flagged here for Phase C/F revisit. Verified live on `--dry-run --today 2026-05-30`.
- **Bot-author commit identity.** Daily workflow commits as `long-way-bot <long-way-bot@users.noreply.github.com>`. Owner may want a stronger marker (e.g. signed commits) once Phase E's dashboard is the public-facing artifact.

## Phase A "Done when" gate — VERIFIED ✅
Production project has 2 tasks dated 2026-05-04. Re-trigger via `workflow_dispatch` shows 0 new (cache hit). LOG.md committed by bot. See repo at https://github.com/SauravSuresh/long-way-engine.

## Phase B "Done when" gate — VERIFIED ✅
Per spec: `today=Friday` produces Friday review; `today=Sunday` produces zero; `today=last-Saturday-of-month` produces monthly retrieval; `paused: true` produces zero of any kind. All eight matrix dates verified by template-ID assertion (not just count) including the 2029-04-01 Sunday-quarterly interaction.

## Phase C entry points

Phase C = reflections subsystem.

- `reflections/` directory tree with `.gitkeep` files (`weekly/`, `monthly/`, `quarterly/`, `annual/`, `debugging/`, `pairing/`, `private/`).
- `reflections/private/` already in `.gitignore`.
- `src/reflections.py` — given a template and a date, write the stub markdown file at the resolved path *if it doesn't already exist*. Never overwrite. Frontmatter: `type`, `date`, `iso_week` / month / quarter equivalent, `status: stub`, `word_count: 0`.
- `src/templates.py` — extend variable resolver with `{iso_year}`, `{iso_week:02d}`, `{year}`, `{month:02d}`, `{quarter}`, `{quarter_num}` so `stub_path` strings resolve at run time.
- `src/main.py` — when a created (or marker-rehydrated) template carries `reflection.create_stub: true`, also create the stub file. Add to LOG.md summary line.
- A small utility (likely a step in `main.py`) updates `word_count` and `status` for all reflections each run, by reading current word counts via the `markdown` package. `status: stub | filled` toggles automatically when word count exceeds template baseline by some threshold (or owner manually sets `status: filled`).
- Tests: stub creation idempotent (no overwrite), frontmatter parsing, word-count updating, path resolution edge case (ISO week year boundary 2026-12-31 → 2027-W53 file).

## Constraints holding

- Python ≥3.11. Stdlib + `requests`, `PyYAML`, `markdown`, `pytest`. No frameworks, no async, no ORMs.
- One system-clock injection point: `src/clock.py:29`.
- Token never logged. `logging` everywhere; `print` only for CLI table output.
- Daily-run client write-only on task state; idempotency reads permitted; destructive ops on a separate class.
- Owner TZ everywhere via `Clock(state.timezone)`. UTC only for `created_at` cache stamps.
- Pin to Todoist API v1; paginated list responses follow `next_cursor`.

— end of Phase B —
