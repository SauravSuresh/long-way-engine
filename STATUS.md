# STATUS

Phases A through D complete. 214 tests passing locally and in CI.

**Phase E plan drafted in conversation (2026-05-04). Not yet implemented.** Full plan preserved at the bottom of this file under "Phase E plan (approved, pending implementation)" and the conversation transcript is at `transcripts/phase-d-e.jsonl`.

## Phase A — walking skeleton + CLI retrofit *(2026-05-04)*

End-to-end happy path. Two daily Todoist tasks created from templates, idempotent across reruns, scheduled via GitHub Actions cron. Local CLI added: `--dry-run`, `--today`, `--project-id`, `--cache-file`, `--verbose`, `--cleanup-project [--yes]`.

### Amendment to the original "write-only Phase A" constraint

Daily-run client is **write-only on TASK STATE**. Idempotency reads (a single GET per run for marker dedup, lazy + memoized) are permitted. Phase E's completion API stays strictly separate. Destructive operations live on a separate `TodoistAdminClient` invoked only by `--cleanup-project`.

## Phase B — all ritual cadences *(2026-05-04)*

Cadence dispatch: `paused` short-circuit, `daily`, `weekly`, `monthly` (int 1–28 / `last-day` / `last-saturday`), `quarterly`, `annual`. Sunday-off applies only to `daily`. The 2029-04-01 Sun-quarter-boundary edge case is a regression test.

## Phase C — reflections subsystem *(2026-05-04)*

Templates bridge to version-controlled markdown reflections. `create_stub` is template-fired (not task-creation-fired), idempotent, never overwrites. `update_metadata` walks the four cadence dirs, edge-trigger toggles `stub` → `filled` on upward crossing of `baseline + 50` words. Manual `status: stub` reverts stick until prose drops and re-crosses upward. Walk runs even when paused (pause stops new generation, not maintenance).

## Phase D — active practices + module work *(2026-05-04)*

Module trunk and active-practice templates wired in.

- **Active practices** — 5 templates (`task_templates/practices.yaml`):
  weekly trace-one-thing (Sunday), weekly read-real-code (Saturday), weekly pair-with-engineer (Thursday), monthly OSS PR (day 15), quarterly build-the-thing-under-the-thing.
- **Module trunk** — 30 templates (`task_templates/modules.yaml`): 23 onboarding tasks (modules 1–23) + 7 lineage detours (modules 6, 7, 10, 12, 14, 16, 21). All `cadence: once-per-module`, dispatched by `module_number == state.current_module`. Module-keyed `external_id` keeps cache + marker dedup independent from date.
- **Pair-day collision avoidance** — `daily-evening-hands-on` now has `skip_if: [sunday, pair_day]`. `pair_day: thursday` in `config.yaml` means Thursday's solo evening hands-on auto-skips so the pair session replaces it.
- **Multi-rule `skip_if`** — Template's `skip_if` is now a `list[str]`. Loader normalizes single-string YAML to a one-element list (backward-compatible).
- **`{current_book}` fallback chain** — `state.current_book` is the override; otherwise `syllabus.current_book(state.month)` resolves from a hand-written `PRIMARY_BOOK_BY_MONTH` table covering months 1–39. Carry-forward for unmapped months.
- **Syllabus parser** — regex extractor over the four "Phase X reading" sections of `the-long-way.md`. Used both for the dashboard (Phase E) and a **drift sanity test** that cross-checks every `PRIMARY_BOOK_BY_MONTH` value substring-matches a regex-extracted title (after `lower()` + non-alnum collapse — robust to smart quotes, em-dashes, colons).

## What works

### Code
- `src/ids.py` — deterministic SHA256 `external_id(template_id, due_date)` and `module_external_id(template_id, module_number)`.
- `src/cache.py` — JSON cache with atomic write, corruption tolerance, 60-day pruning. `prune` requires `now=`.
- `src/clock.py` — single injection point. `Clock(tz)` for production, `FrozenClock(when, tz)` for tests/CLI. `grep -rn "datetime\.now\|date\.today\|time\.time" src/` returns one line.
- `src/config.py` — yaml + `.env` loader, token redaction. Phase D adds `pair_day: str | None`.
- `src/state.py` — required keys, ZoneInfo, date checking. `current_book` is optional override.
- `src/syllabus.py` *(Phase D)* — `parse_books(text)` regex extractor; `PRIMARY_BOOK_BY_MONTH` (months 1–39); `current_book(month)` with carry-forward; `normalize_for_drift_check` for the cross-check.
- `src/templates.py` — loads YAML, resolves placeholders. **Phase B** added `day_of_week`, `day_of_month`. **Phase C** added date-derived placeholders + format-spec syntax. **Phase D** added `module_number`; `skip_if` is now `list[str]`; `_lookup('current_book')` chains `state.current_book` → `syllabus.current_book(state.month)`.
- `src/scheduler.py` — Phase B cadence dispatch + paused short-circuit. **Phase D** wires `once-per-module` (returns `template.module_number == state.current_module`) and `skip_if=pair_day` (skips on `config.pair_day` weekday). Multi-rule `skip_if` iterated.
- `src/todoist.py` — `TodoistClient.create_task_idempotent` with marker dedup + lazy memoized GET. `TodoistAdminClient` for `--cleanup-project`.
- `src/reflections.py` — `create_stub`, `update_metadata`, edge-triggered toggle, never-overwrite.
- `src/main.py` — orchestrates one run. **Phase D**: dispatches between `external_id` (date-keyed) and `module_external_id` (module-keyed) based on cadence. `_classify_skip` extended with `SKIP (pair day)` and `SKIP (not current module)`.

### Configuration
- `config.yaml` — real Todoist project ID; `ritual_times` (incl. `sunday_trace`); `sunday_off: true`; `pair_day: thursday`.
- `state.yaml` — `current_module`, `month`, optional `current_book`, scaffolded `completed_modules` (Phase E reads).

### Templates *(40 task + 4 reflection)*
- daily: 3 (morning reading, anki, evening hands-on with `skip_if: [sunday, pair_day]`)
- weekly: 2 ritual + 3 practices = 5
- monthly: 3 ritual + 1 practice = 4
- quarterly: 1 synthesis + 1 build-thing-under-thing = 2
- annual: 1
- modules: 23 onboarding + 7 lineage = 30
- reflection skeletons (markdown): 4

### Tests *(214 passing)*
- `tests/test_ids.py` — 5
- `tests/test_cache.py` — 7
- `tests/test_clock.py` — 6
- `tests/test_config.py` — 9
- `tests/test_state.py` — 4
- `tests/test_templates.py` — 20 (Phase D adds: `module_number` parsed, `current_book` override + syllabus fallback + carry-forward)
- `tests/test_scheduler.py` — 60 (Phase D adds 12: once-per-module match/mismatch/lineage+onboarding both fire/missing module_number/paused-blocks-without-raising; `skip_if=pair_day` configured/unset/typo/multi-rule)
- `tests/test_todoist.py` — 25
- `tests/test_main.py` — 4
- `tests/test_main_cli.py` — 28
- `tests/test_reflections.py` — 24
- `tests/test_syllabus.py` *(Phase D, new)* — 15 (parse_books extracts known books, regex handles single/range months and reference-only entries; `PRIMARY_BOOK_BY_MONTH` covers 1–39; `current_book(1)` = CSAPP, `current_book(7)` = Networking, carry-forward at 11; **drift sanity check** with normalization)

### CI / scheduling
- `.github/workflows/test.yml` — pytest on PRs + pushes to main.
- `.github/workflows/daily.yml` — `cron: "30 21 * * *"` (03:00 IST) + `workflow_dispatch`. Reads `secrets.TODOIST_TOKEN`. Commits cache, LOG.md, and any new reflection stubs.

## What is stubbed / deliberately deferred

- **Completion API (`get_completion_status`).** Phase E. Marker-dedup reads exist but list active tasks for a project — different concern, different endpoint.
- **Dashboard.** No `docs/`, no `src/dashboard.py`, no `data.json`. Phase E.
- **Module advancement automation.** `state.current_module` advances manually (owner edits state.yaml at month/module boundaries). Same discipline as `state.month`. No engine-driven advancement.
- **`completed_modules` consumption.** Field exists in state.yaml as an empty list; the engine doesn't read it. Phase E's dashboard does.
- **`rebuild_cache.py` (Phase F script).** Runtime marker dedup handles cache loss; Phase F's offline script handles the long tail.
- **`dry_run` workflow input.** Local CLI has it. Surfacing as a `workflow_dispatch` input is Phase F.

## UX flags worth tracking

- **Last-Saturday triple-firing (Phase B+C).** Three Saturday-time tasks fire on last-Saturdays: `weekly-saturday-deep-block`, `monthly-retrieval`, `monthly-review`. Phase C adds that monthly-retrieval and monthly-review *share* a stub path (one stub per month). Owner may eventually want weekly-Saturday deep block to skip last-Saturdays. Not a Phase D fix.
- **Last-Saturday + `weekly-read-real-code` quadruple-firing (Phase D).** `weekly-read-real-code` is also Saturday at saturday_deep_block time. So last-Saturdays now have FOUR Saturday-time tasks landing simultaneously: read-real-code, deep-block, monthly-retrieval, monthly-review. Same UX flag as above — Phase F revisit.
- **Pair-day on holiday weeks.** If `pair_day: thursday` and a holiday lands on Thursday, the pair session and the solo evening hands-on both skip silently. No catch-up logic — owner sees an empty Thursday and decides what to do.
- **Threshold tuning** (Phase C). `WORD_COUNT_THRESHOLD = 50`. Single number to bisect if auto-toggle ever feels wrong.
- **Drift sanity test scope.** Catches missing entries, not stale ones. If syllabus `*Foo* — Author *(months 5–8)*` is removed, but `PRIMARY_BOOK_BY_MONTH[5] = "Foo"` stays, the test still passes. Best-effort only.

## Phase A "Done when" gate — VERIFIED ✅
Production project has 2 tasks dated 2026-05-04. workflow_dispatch re-trigger shows 0 new (cache hit).

## Phase B "Done when" gate — VERIFIED ✅
8-date matrix verified by template-ID assertion incl. 2029-04-01 Sun + Q2 boundary.

## Phase C "Done when" gate — VERIFIED ✅
Live sandbox: stub created, edited, walk flipped status to filled at the threshold crossing, owner prose preserved.

## Phase D "Done when" gate — VERIFIED ✅

Per spec + your additions:

| Probe | Expected | Result |
|---|---|---|
| `state.current_module=1` | module-01-onboarding fires | ✅ |
| `state.current_module=1 → 2` advance | module-02-onboarding fires; module-01 NOT in fired list | ✅ |
| `state.current_module=6` | module-06-onboarding + module-06-lineage both fire | ✅ |
| `state.current_module=7` | module-07-onboarding + module-07-lineage both fire (separate from 6) | ✅ |
| `state.month=1` | morning reading title = "Morning reading: Computer Systems: A Programmer's Perspective" | ✅ |
| `state.month=7` | morning reading title = "Morning reading: Computer Networking: A Top-Down Approach" | ✅ |
| `state.month=11` | morning reading title carries forward Networking | ✅ |
| `state.current_book="X"` | morning reading title = "Morning reading: X" (override beats syllabus) | ✅ |
| Thursday | pair fires, evening-hands-on SKIP (pair day) | ✅ |
| Sunday | trace fires, all dailies SKIP (Sunday) | ✅ |

"Fired" is asserted as the set of WOULD CREATE rows in the dry-run table — never absence-from-table — so SKIP rows for non-current modules don't get conflated with creation.

## Phase E entry points

Phase E = read-only completion + dashboard.

- `src/todoist.py` extended with `get_completion_status(task_ids)`. Strict separation: no shared retry/session helpers with `create_task_idempotent` or the marker-dedup GET. Add a regression test asserting the symbols don't share a private helper module.
- `.completion_cache.json` for 6-hour TTL caching.
- `src/dashboard.py` — pure function `(state, completion_data, reflection_listing, books) -> html_string`.
- `docs/index.html`, `docs/assets/style.css`, `docs/assets/data.json` written each run.
- All seven dashboard sections: header, streaks (daily / weekly review / monthly post), phase + module progress bar, reflection log (reverse-chrono with status/word_count), active practice tracker (manual_counters + computed), books per phase (using `parse_books` from Phase D + state.books_state for reading state), last-7-days timeline.
- Books reading state: `books_state` field added to `state.yaml`, hand-edited by owner.
- Streak walks: walk back from today, per-streak completion-cache lookups against the four cadence external_ids.
- GH Pages enablement on `docs/` (manual repo-settings step in README).
- HTML snapshot tests on representative state shapes.

## Constraints holding

- Python ≥3.11. Stdlib + `requests`, `PyYAML`, `markdown`, `pytest`. No frameworks, no async, no ORMs.
- One system-clock injection point: `src/clock.py:29`.
- Token never logged. `logging` everywhere; `print` only for CLI table output.
- Daily-run client write-only on task state; idempotency reads permitted; destructive ops on a separate class.
- Owner TZ everywhere via `Clock(state.timezone)`. UTC only for `created_at` cache stamps.
- Pin to Todoist API v1; paginated list responses follow `next_cursor`.
- Engine reads/writes only `reflections/{weekly,monthly,quarterly,annual}/`. `private/`, `debugging/`, `pairing/` are owner-only.
- `state.current_module` and `state.month` are owner-managed (manual advancement at module/month boundaries). Engine never writes to `state.yaml`.

— end of Phase D —

---

# Phase E plan (approved, pending implementation)

*(Drafted 2026-05-04 over a power outage. Approved by owner. Implementation deferred. Full conversation transcript at `transcripts/phase-d-e.jsonl`.)*

## Scope

Read-only completion API + dashboard. Eight sections per spec, no creep. Page < 1 second load, < 100 KB total weight.

## Decisions baked in (from the questions exchange)

1. **`get_completion_status` returns `dict[str, bool]`.** Two-state per spec; True=completed, False=active-or-missing.
2. **Strict isolation.** New class `TodoistCompletionClient` in `src/todoist.py` mirroring `TodoistAdminClient`'s pattern. Own `requests.Session`, own retry helper, own headers method. Module docstring asserts no shared code with `TodoistClient`. Regression test scans private-method names on both classes; intersection (excluding dunders) must be empty.
3. **`.completion_cache.json`.** `{"fetched_at": iso, "completed_ids": [...]}`. 6h TTL. Set membership for O(1) lookup.
4. **Bulk fetch.** One paginated GET against the v1 completed-tasks endpoint over a date window, intersect with our task IDs. **Probe live before implementing** — if the endpoint doesn't support a window query, fall back to per-day pagination but still bulk-per-day, never per-id.
5. **Daily streak walks back from yesterday.** Today's tasks may not be done yet at 03:00 IST cron. Don't punish.
6. **Sundays + pause windows skip in streak walks.** Closed-interval pause_history matches the Sunday rule — both treated as "not counted as a break."
7. **Pause-history schema.** `pause_history: list[{start, end, reason}]` and `paused_since: date | None`. The toggle ritual:
   - Pausing: set `paused: true` AND `paused_since: <today>`.
   - Unpausing: append `{start: paused_since, end: today, reason}` to `pause_history`, set `paused: false`, clear `paused_since`.
   - Currently-paused indefinite period uses `paused_since` directly (no closed interval yet).
   - State loader defaults `pause_history: []`, `paused_since: None`, `books_state: {}` when absent — Phase A–D states keep loading.
8. **Weekly review streak**: Todoist completion AND `status: filled` on the week's reflection file. Both required.
9. **Monthly post streak**: Todoist completion of `monthly-blog-post` only. No reflection check.
10. **HTML rendering**: pure Python f-strings, one function per section in `src/dashboard.py`. No Jinja.
11. **CSS**: single hand-written `docs/assets/style.css`, ~120 lines, system font stack, no external resources, `@media print` styles.
12. **Progress bar**: plain `<div>` with absolute-positioned phase ticks at 1 / 13 / 21 / 31 / 39 percent; current-month marker on top.
13. **Reflection log link target**: `https://github.com/{github_username}/{repo_name}/blob/main/reflections/{type}/{file}.md`.
14. **Last-7-days timeline colors**: green=both anki + morning_reading completed; yellow=one of two; red=neither; gray=Sunday OR inside `pause_history` OR (paused AND date >= paused_since). Evening-hands-on excluded (pair-day variability).
15. **`books_state`**: `{title: not_started | current | done}` map, owner-maintained.
16. **Practice tracker**: `weekly-read-real-code` completion count for code-reading sessions; other three from `manual_counters`.
17. **Render hook**: in `main.run()` after metadata walk, before `append_log`. Wrapped in try/except. Failure logs but doesn't fail the run (per spec Failure Modes table).
18. **`--skip-dashboard` CLI flag**, default render.
19. **Workflow `git add` extends to `docs/index.html` and `docs/assets/data.json`.** CSS committed once, not regenerated each run.
20. **`docs/assets/data.json`** sidecar — same data the renderer used.
21. **Dashboard regenerates even when paused** (per Phase A spec failure-modes: "Pause should not freeze the dashboard").
22. **Snapshot fixtures**: four — `empty.html`, `partial.html`, `full.html`, `paused.html` (current pause + at least one past pause interval, verifies streak preservation).
23. **GH Pages**: manual one-time enablement. README block; click-through by owner.
24. **Performance budget**: check at end. With one HTML + one CSS + one JSON + zero externals, trivially under 100 KB.
25. **Eight sections, no creep.**

## Files to change

**New code:**
- `src/streaks.py` — `daily_streak`, `weekly_review_streak`, `monthly_post_streak`, `_is_skipped_on(date, state)`, `_external_id_for_daily`. Walk starts at `today - 1`.
- `src/dashboard.py` — `render(state, config, completion_set, reflections, books, today, clock) -> tuple[str_html, dict_data_json]`. One function per section: `_header`, `_streaks`, `_progress_bar`, `_reflection_log`, `_practice_tracker`, `_books`, `_last_7_days`, `_footer`. Helpers: `_github_blob_url`, `_paused_summary`.
- `tests/fixtures/dashboard/{empty,partial,full,paused}.html` — snapshot fixtures.

**Modified code:**
- `src/state.py` — `State` gains `paused_since: date | None`, `pause_history: list[PauseInterval]`, `books_state: dict[str, str]`. New `PauseInterval` dataclass (`start`, `end`, `reason`). Loader defaults to empty/None when missing. Validates `start <= end` on intervals.
- `src/todoist.py` — `TodoistCompletionClient` class. Strict isolation per (2). Method `get_completion_status(task_ids: list[str]) -> dict[str, bool]`. Reads/writes `.completion_cache.json` with 6h TTL.
- `src/main.py` — `--skip-dashboard` flag; render hook + try/except; `RunSummary.dashboard_status: "ok"|"error"|"skipped"|None`; `append_log` adds "Dashboard: <status>" line.
- `.github/workflows/daily.yml` — `git add docs/index.html docs/assets/data.json` (CSS untouched on subsequent runs).

**New data:**
- `docs/index.html` — generated each run.
- `docs/assets/style.css` — committed once at Phase E setup.
- `docs/assets/data.json` — generated each run.
- `.gitignore` — confirm `.completion_cache.json` is listed (already there from Phase A scaffold).

**README updates:**
- Pause/unpause ritual section with the toggle dance.
- `books_state` schema + how to update.
- GitHub Pages enablement: Settings → Pages → Source: "Deploy from a branch" → Branch: `main` / `/docs`.

## Implementation order (commits)

1. `state: pause_history, paused_since, books_state with default-if-absent loader`
2. `todoist: TodoistCompletionClient with strict isolation`
3. `streaks: pure-function streak walkers with pause + Sunday handling`
4. `dashboard: renderer + CSS + four snapshot fixtures`
5. `main: wire dashboard into run, --skip-dashboard flag, workflow commits docs/`
6. `docs: README pause ritual + GH Pages instructions; STATUS for Phase F handoff`

## Verification gate

Local:
- `python -m src.main --dry-run` — does NOT generate dashboard.
- `python -m src.main --skip-dashboard` — `docs/index.html` not modified.
- Real run — `docs/index.html` regenerated with current streaks + reflection log + books panel; `data.json` matches.
- Toggle `paused: true` + `paused_since: 2026-05-04` → header shows "Paused since 2026-05-04 (0 days)". Past streak preserved.
- Add fake `pause_history: [{start: 2026-04-15, end: 2026-04-30, reason: "test"}]` → daily streak walking back across April 15–30 doesn't break.
- All 4 snapshot tests pass.

GH:
- Pages enabled → dashboard at `https://sauravsuresh.github.io/long-way-engine/`.
- Page weight under 100 KB.

## Open notes for the next session

- **Live API probe before implementing.** The Todoist v1 completed-tasks endpoint shape is unknown. One-shot probe with the production token (against the sandbox project) before committing the client.
- **Dashboard byte-equality snapshots.** Renderer must be deterministic — Clock-driven, no `datetime.now()`, no random ordering.
- **`docs/assets/style.css` lifecycle.** Generated once when absent; left untouched after. Owner can hand-edit for visual tweaks.
- **`books_state` initial seed.** Add an example covering Phase 1 books (CSAPP=current, Networking=not_started, Debugging=not_started).

— end of Phase E plan —
