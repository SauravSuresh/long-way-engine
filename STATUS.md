# STATUS

Phases A through C complete. Production daily run validated end-to-end (cron + workflow_dispatch). Reflection lifecycle (create → edit → walk → toggle) verified live against the sandbox project. 182 tests passing locally and in CI.

## Phase A — walking skeleton + CLI retrofit *(2026-05-04)*

End-to-end happy path: two daily Todoist tasks created from templates, idempotent across reruns, tested with mocked HTTP, scheduled via GitHub Actions cron.

### Amendment to the original "write-only Phase A" constraint

**Original wording (PROMPT.md / SPEC.md):** *"Strict read/write separation in todoist.py. Phase A is write-only on Todoist."*

**Amended interpretation:** the daily-run client is **write-only on TASK STATE** (no PATCH, no DELETE, no POST outside `create_task_idempotent`). **Idempotency reads are permitted**: a single GET to list project tasks and parse content markers, fired lazily on the first cache miss and memoized for the rest of the run. Without this, the spec's "two-layer dedup" was a half-feature: the marker is written but never read until Phase F's `rebuild_cache.py`, which means a deleted/corrupt cache file would silently duplicate tasks. The amendment makes the marker layer load-bearing at runtime.

The Phase E completion API (`get_completion_status`) is still strictly separate — must not share a retry wrapper, helper, or session-scoped state with `create_task_idempotent`.

Destructive operations (DELETE) live on a *separate class* `TodoistAdminClient` invoked only by the `--cleanup-project` CLI subcommand.

## Phase B — all ritual cadences *(2026-05-04)*

Cadence dispatch in the scheduler (`paused`, `daily`, `weekly`, `monthly`, `quarterly`, `annual`), plus the matching ritual templates parsed from the syllabus.

## Phase C — reflections subsystem *(2026-05-04)*

Tasks now bridge to version-controlled markdown reflections.

- **Cadence-based reflection templates** in `reflection_templates/{weekly,monthly,quarterly,annual}.md`.
- **Stub creation** is template-fired (not task-creation-fired): runs whenever a template would fire, regardless of whether the task was newly created, marker-deduped, or cache-hit. Never overwrites an existing file.
- **Edge-triggered status toggle**: `stub` flips to `filled` only on an *upward crossing* of `baseline + 50` words. Old `word_count` from frontmatter is the lower side of the comparison. This makes manual `status: stub` reverts sticky — they hold until the count drops below threshold and rises again.
- **Metadata walk** runs unconditionally at the end of every run, including paused runs. Pause stops new generation, not maintenance of existing stubs.
- **Per-run pending-paths set** in dry-run only: when two templates point at the same path (e.g. `monthly-retrieval` and `monthly-review` both at `reflections/monthly/2026-05.md` on last-Saturdays), the first prints `WOULD CREATE STUB`, the second prints `WOULD SKIP STUB (pending)`. Real runs use the disk as source of truth — no pending set needed.
- **Variable resolver** extended with `{year}`, `{month:02d}`, `{date}`, `{iso_year}`, `{iso_week:02d}`, `{quarter}` (1–4 from month). Format spec syntax `{name:fmt}` supported. Confirmed against the 2027-01-01 ISO-W53/2026 boundary.
- **Owner-only directories** (`reflections/private/`, `debugging/`, `pairing/`) are never read or written by the engine.

## What works

### Code
- `src/ids.py` — deterministic SHA256-based `external_id`. `module_external_id` shape for Phase D.
- `src/cache.py` — JSON cache with atomic write, corruption tolerance, 60-day pruning. `prune` requires `now=` (no system-clock fallback).
- `src/clock.py` — single injection point for the system clock. `Clock(tz)` for production, `FrozenClock(when, tz)` for tests and `--today`. `grep -rn "datetime\.now\|date\.today\|time\.time" src/` returns exactly one line.
- `src/config.py` — yaml + `.env` loader, token redaction at repr and via `TokenRedactingFilter`.
- `src/state.py` — loads and validates `state.yaml`. Required keys, ZoneInfo, date checking. Schema scaffolds Phase D–F fields.
- `src/templates.py` — loads `task_templates/*.yaml`, resolves placeholders. **Phase B** added `day_of_week`, `day_of_month`. **Phase C** added date-derived placeholders (`{year}`, `{month:02d}`, `{iso_year}`, `{iso_week:02d}`, `{quarter}`, `{date}`) and the `{name:fmt}` format-spec syntax. Unknown YAML fields stay in `template.raw` for forward-compat.
- `src/scheduler.py` — Phase B cadence dispatch with `paused` short-circuit; calendar-based weekly day matching (verified across ISO week boundary); monthly int 1–28 / `last-day` / `last-saturday`; quarterly Jan/Apr/Jul/Oct 1; annual Jan 1; the 2029-04-01 Sun + Q2 boundary regression test.
- `src/todoist.py` — `TodoistClient.create_task_idempotent`. Cache hit = zero API calls; cache miss = up to one GET (memoized) for marker dedup, then one POST. Marker hit *rehydrates the in-memory cache*. Retries 3× on 5xx. Endpoint base: `https://api.todoist.com/api/v1`. Module docstring + regression test enforce no PATCH/DELETE on the daily-run client. `TodoistAdminClient` for `--cleanup-project`.
- `src/reflections.py` *(new in Phase C)* — `create_stub` (idempotent, never overwrites, dry-run safe, pending-paths-aware), `update_metadata` (walks four cadence dirs only, edge-triggered toggle, malformed-frontmatter tolerance), helpers `split_frontmatter`, `render_frontmatter`, `count_words_in_body`, `_baseline_word_count` (LRU-cached, naive frontmatter strip for unresolved templates), `_strip_frontmatter_naively`.
- `src/main.py` — orchestrates one run: load config + state + templates → today in owner TZ → for each template `should_create_today` → resolve variables → check cache → check marker layer → create task → **create_stub** → update cache → prune → save → **update_metadata walk** → append `LOG.md`. CLI: `--dry-run`, `--today`, `--project-id`, `--cache-file`, `--verbose`, `--cleanup-project ID [--yes]`. Dry-run table now has a second `REFLECTION STUBS` section. LOG.md gains "Reflection stubs created" and "Reflection metadata updated" lines.

### Configuration
- `state.yaml` — `start_date: 2026-05-04`, timezone `Asia/Kolkata`, `current_book` hardcoded (Phase D replaces with parser).
- `config.yaml` — real Todoist project ID, real github_username, all five ritual times, full label set.
- `.env.example` + `.env` (gitignored) + `TODOIST_TOKEN` GitHub repo secret.

### Templates *(10 task + 4 reflection)*
- `task_templates/daily.yaml` — `daily-morning-reading`, `daily-anki`, `daily-evening-hands-on`.
- `task_templates/weekly.yaml` — `weekly-friday-review` (with stub), `weekly-saturday-deep-block`.
- `task_templates/monthly.yaml` — `monthly-blog-post` (day 1), `monthly-retrieval` (last Sat, with stub), `monthly-review` (last Sat, with stub at the same path).
- `task_templates/quarterly.yaml` — `quarterly-synthesis` (with stub).
- `task_templates/annual.yaml` — `annual-review` (with stub).
- `reflection_templates/{weekly,monthly,quarterly,annual}.md` — owner-editable markdown skeletons with placeholder frontmatter.

### Tests *(182 passing)*
- `tests/test_ids.py` — 5
- `tests/test_cache.py` — 7
- `tests/test_clock.py` — 6
- `tests/test_config.py` — 9
- `tests/test_state.py` — 4
- `tests/test_templates.py` — 16 (including ISO week boundary, quarter-month parametrize)
- `tests/test_scheduler.py` — 48 (paused-blocks-each-cadence, 2029-04-01 edge case, last-saturday, ISO week boundary)
- `tests/test_todoist.py` — 25 (marker dedup, lazy memoization, pagination, admin client, no destructive methods)
- `tests/test_main.py` — 4
- `tests/test_main_cli.py` — 28 (incl. paused dry-run all SKIP (paused), paused real-run still writes cache+log, **Friday creates weekly stub, dry-run shows stub table, last-Saturday pending collision, paused metadata walk still updates, ordering: walk runs after creation**)
- `tests/test_reflections.py` *(new)* — 24 (frontmatter parser edge cases, never-overwrite invariant, dry-run filesystem safety, **off-by-one toggle baseline+49 stub vs baseline+50 filled**, one-way filled persistence, **manual revert stickiness**, manual-revert-then-recross flip cycle, owner-only dirs untouched)

### CI / scheduling
- `.github/workflows/test.yml` — pytest on PRs + pushes to main, Python 3.11.
- `.github/workflows/daily.yml` — `cron: "30 21 * * *"` (03:00 IST) + `workflow_dispatch`. Reads `secrets.TODOIST_TOKEN`. Commits `.task_cache.json`, `LOG.md`, and any new reflection stubs.

## What is stubbed / deliberately deferred

- **Completion API (`get_completion_status`).** Phase E. Marker-dedup reads exist but list active tasks for a project, not completion state.
- **Module / once-per-module cadence.** `module_external_id` exists in `src/ids.py`; scheduler raises `NotImplementedError`. Phase D wires it.
- **Syllabus parser.** `current_book` is hardcoded in `state.yaml`. Phase D adds `src/syllabus.py`.
- **Dashboard.** No `docs/`, no `src/dashboard.py`, no `data.json`. Phase E.
- **`rebuild_cache.py` (Phase F).** Runtime marker dedup handles cache loss; Phase F's offline script handles the long tail (older days outside the prune window, completed tasks).
- **`dry_run` workflow input.** Local CLI has `--dry-run`. Surfacing it as a `workflow_dispatch` input is Phase F.

## UX flags worth tracking

- **Last-Saturday triple-firing (Phase B + C).** On the last Saturday of any month, three Saturday-time tasks fire simultaneously: `weekly-saturday-deep-block` + `monthly-retrieval` + `monthly-review`. Phase C adds the wrinkle that monthly-retrieval and monthly-review now *share* a reflection path — exactly one `2026-05.md` stub gets created per month, but two tasks land in Todoist at the same time. Owner may eventually want `weekly-saturday-deep-block` to skip on last-Saturdays so the monthly tasks subsume it. Not a Phase C fix — flagged here for Phase F revisit.
- **Bot-author commit identity.** Daily workflow commits as `long-way-bot <long-way-bot@users.noreply.github.com>`. Owner may want a stronger marker (e.g. signed commits) once Phase E's dashboard is the public-facing artifact.
- **Threshold tuning.** `WORD_COUNT_THRESHOLD = 50`. Documented in `reflections/README.md`. If the auto-toggle feels wrong in either direction (e.g. weekly reviews crossing too easily because the prompt-list is short), this is the single number to bisect.

## Phase A "Done when" gate — VERIFIED ✅
Production project has 2 tasks dated 2026-05-04. Re-trigger via `workflow_dispatch` shows 0 new (cache hit). LOG.md committed by bot.

## Phase B "Done when" gate — VERIFIED ✅
Per spec: `today=Friday` produces Friday review; `today=Sunday` produces zero; `today=last-Saturday-of-month` produces monthly retrieval; `paused: true` produces zero of any kind. All eight matrix dates verified by template-ID assertion (not just count) including the 2029-04-01 Sunday-quarterly interaction.

## Phase C "Done when" gate — VERIFIED ✅
Per spec: *"Friday's run creates `reflections/weekly/2026-W14.md` as a stub *and* the Todoist task. Editing the file and re-running updates `word_count` and toggles `status` to `filled`. Re-running with the file already present does not clobber it."*

Live sandbox verification:
1. Empty `reflections/weekly/`, ran `--today 2026-05-08 --project-id <SANDBOX>` → stub created at `reflections/weekly/2026-W19.md` with `status: stub, word_count: 38` (post-walk baseline). 4 sandbox tasks created.
2. Appended ~60 words of prose to the stub.
3. Re-ran same date → log shows `status stub -> filled (word_count 38 -> 101, threshold 88)`. Stub now `status: filled, word_count: 101`. Owner prose preserved verbatim. Cache hits all 4 tasks.

Plus dry-run probes for: ISO-W53/2026 boundary (`2027-01-01 → reflections/weekly/2026-W53.md`), Jan 1 multi-cadence stack (annual + quarterly + monthly stubs all listed), last-Saturday pending collision (one CREATE + one SKIP (pending) for the shared monthly path).

## Phase D entry points

Phase D = active practices and module work.

- `task_templates/practices.yaml` — weekly trace-one-thing (Sunday), Saturday code-reading, monthly OSS PR, quarterly build-the-thing, continuous debug-deliberately reminder.
- `task_templates/modules.yaml` — one entry per syllabus module (1–23) with `cadence: once-per-module`, optional `lineage_detour` sub-task.
- `src/syllabus.py` — minimal regex extractor for "Phase X reading" sections from `the-long-way.md`. Replaces hardcoded `state.current_book` with a lookup keyed on `state.month`.
- `src/scheduler.py` — wire `cadence: once-per-module` (currently raises NotImplementedError). Uses `module_external_id(template_id, module_number)` for ID generation. Cache miss is the trigger: advancing `state.current_module` from 1 to 2 makes module 2's onboarding task miss the cache, causing creation; subsequent runs see the cache hit.
- `src/main.py` — pass `state.current_module` and `state.completed_modules` to the scheduler.
- Tests: module advancement creates exactly one onboarding task; advancing again before completion does not duplicate; `{current_book}` resolves correctly across all four phases per syllabus reading schedule.

## Constraints holding

- Python ≥3.11. Stdlib + `requests`, `PyYAML`, `markdown`, `pytest`. No frameworks, no async, no ORMs.
- One system-clock injection point: `src/clock.py:29`.
- Token never logged. `logging` everywhere; `print` only for CLI table output.
- Daily-run client write-only on task state; idempotency reads permitted; destructive ops on a separate class.
- Owner TZ everywhere via `Clock(state.timezone)`. UTC only for `created_at` cache stamps.
- Pin to Todoist API v1; paginated list responses follow `next_cursor`.
- Engine reads/writes only `reflections/{weekly,monthly,quarterly,annual}/`. `private/`, `debugging/`, `pairing/` are owner-only.

— end of Phase C —
