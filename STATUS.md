# STATUS

Phases A through E complete. 282 tests passing locally and in CI.

## Phase A — walking skeleton + CLI retrofit *(2026-05-04)*

End-to-end happy path. Two daily Todoist tasks created from templates, idempotent across reruns, scheduled via GitHub Actions cron. Local CLI added: `--dry-run`, `--today`, `--project-id`, `--cache-file`, `--verbose`, `--cleanup-project [--yes]`.

### Amendment to the original "write-only Phase A" constraint

Daily-run client is **write-only on TASK STATE**. Idempotency reads (a single GET per run for marker dedup, lazy + memoized) are permitted. Phase E's completion API stays strictly separate. Destructive operations live on a separate `TodoistAdminClient` invoked only by `--cleanup-project`.

## Phase B — all ritual cadences *(2026-05-04)*

Cadence dispatch: `paused` short-circuit, `daily`, `weekly`, `monthly` (int 1–28 / `last-day` / `last-saturday`), `quarterly`, `annual`. Sunday-off applies only to `daily`. The 2029-04-01 Sun-quarter-boundary edge case is a regression test.

## Phase C — reflections subsystem *(2026-05-04)*

Templates bridge to version-controlled markdown reflections. `create_stub` is template-fired (not task-creation-fired), idempotent, never overwrites. `update_metadata` walks the four cadence dirs, edge-trigger toggles `stub` → `filled` on upward crossing of `baseline + 50` words. Manual `status: stub` reverts stick until prose drops and re-crosses upward. Walk runs even when paused (pause stops new generation, not maintenance).

## Phase E — completion API + dashboard *(2026-05-04)*

Read-only completion client + static-HTML dashboard. Eight sections, no creep.

- **`TodoistCompletionClient`** — strictly isolated from the daily-run
  client: own `requests.Session`, own retry helper, own headers method
  (`_completion_headers`, `_completion_get_with_retry`). A regression
  test asserts the private-method intersection between `TodoistClient`
  and `TodoistCompletionClient` is empty (excluding dunders).
- **6h TTL completion cache** — `.completion_cache.json` schema is
  `{"fetched_at": iso, "completed_ids": [...]}`. Bulk-fetches the v1
  `/tasks/completed/by_completion_date` endpoint over a 90-day window
  paginated via `next_cursor`; intersects locally with the caller's
  task IDs. Tolerates either `items` or `results` response keys —
  endpoint shape is **live-probe TBD** (see Phase F notes below).
- **`src/streaks.py`** — pure-function `daily_streak`,
  `weekly_review_streak`, `monthly_post_streak`. Walk back from
  `today - 1` (decision 5: today's tasks may not be done yet at 03:00
  cron). Skip semantics (decision 6): Sunday-skip applies only to
  daily walker; pause windows skip in all three. Daily requires both
  anki AND morning-reading completed; weekly requires both Todoist
  completion + reflection `status: filled`; monthly is Todoist
  completion only.
- **`src/dashboard.py`** — eight sections: header, streaks,
  progress bar (phase ticks at 1/13/21/31/39%), last-7-days timeline
  (green/yellow/red/gray per decision 14), practice tracker (code
  reading via cache+completion; three more from `manual_counters`),
  books (`parse_books` × `books_state` per phase), reflection log
  (reverse-chrono with GitHub blob links), footer. Pure deterministic
  renderer: `render(state, config, completion_set, cache, reflections,
  books, today, clock, reflections_root) -> (html, data_json)`. CSS
  hand-written, ~120 lines, system fonts, no externals.
- **State schema additions** — `paused_since: date | None`,
  `pause_history: list[PauseInterval]`, `books_state: dict[str, str]`.
  All optional in YAML; the loader defaults to None / [] / {} so
  Phase A–D state files load unchanged. Validates `start <= end` on
  intervals; `books_state` values restricted to `not_started | current
  | done`.
- **Render hook** — `main.run()` after metadata walk, before
  `append_log`. Wrapped in try/except: failure logs but never fails
  the run (decision 17, dashboard_status="error"). Dry-run leaves the
  status `None`; `--skip-dashboard` short-circuits to "skipped".
  Renders even when paused (decision 21).
- **CSS lifecycle** — `write_css_if_absent` lays down
  `docs/assets/style.css` exactly once. The workflow stages
  `docs/index.html` + `docs/assets/data.json` on each run; CSS is
  manually committed at Phase E setup and never regenerated.
- **Snapshot fixtures** — four byte-equal HTML snapshots at
  `tests/fixtures/dashboard/{empty,partial,full,paused}.html`.
  `DASHBOARD_REGEN=1 pytest tests/test_dashboard.py -q` regenerates
  them when intentional changes are made.

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
- `src/main.py` — orchestrates one run. **Phase D**: dispatches between `external_id` (date-keyed) and `module_external_id` (module-keyed) based on cadence. `_classify_skip` extended with `SKIP (pair day)` and `SKIP (not current module)`. **Phase E**: dashboard render hook after metadata walk; `--skip-dashboard` flag; `RunSummary.dashboard_status: "ok" | "error" | "skipped" | None`; `Dashboard:` line in `append_log` output.
- `src/streaks.py` *(Phase E)* — `daily_streak`, `weekly_review_streak`, `monthly_post_streak`, `_is_in_pause_window`, `_is_skipped_on`, `_external_id_for_daily`. Pure functions, walk back from `today - 1`.
- `src/dashboard.py` *(Phase E)* — `render(...) -> (html, data_json)`, `scan_reflections`, `write_css_if_absent`, `CSS` constant, `ReflectionMeta` dataclass, eight per-section private renderers.
- `src/todoist.py` *(Phase E)* — `TodoistCompletionClient` with strict isolation; `_completion_headers`, `_completion_get_with_retry`, `_read_cache_if_fresh`, `_write_cache`, `_fetch_completed_ids`. `.completion_cache.json` 6h TTL.

### Configuration
- `config.yaml` — real Todoist project ID; `ritual_times` (incl. `sunday_trace`); `sunday_off: true`; `pair_day: thursday`.
- `state.yaml` — `current_module`, `month`, optional `current_book`, scaffolded `completed_modules` (Phase E reads). **Phase E** adds optional `paused_since`, `pause_history`, `books_state`; all default-if-absent.

### Templates *(40 task + 4 reflection)*
- daily: 3 (morning reading, anki, evening hands-on with `skip_if: [sunday, pair_day]`)
- weekly: 2 ritual + 3 practices = 5
- monthly: 3 ritual + 1 practice = 4
- quarterly: 1 synthesis + 1 build-thing-under-thing = 2
- annual: 1
- modules: 23 onboarding + 7 lineage = 30
- reflection skeletons (markdown): 4

### Tests *(282 passing)*
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
- `tests/test_state.py` *(Phase E adds 8)* — `paused_since` parses or rejects, `pause_history` rejects inverted intervals + non-date values, `books_state` rejects invalid values, all three default-if-absent.
- `tests/test_todoist.py` *(Phase E adds 11)* — `TodoistCompletionClient` returns `dict[str, bool]`, writes `.completion_cache.json`, hits cache within 6h, refetches at 7h, paginates via `next_cursor`, retries 5xx, raises on 401, tolerates corrupt cache, plus the **no-shared-private-methods** regression test against `TodoistClient`.
- `tests/test_streaks.py` *(Phase E, new)* — 24 (Sunday + pause skip rules, daily walk with partial day breakage, weekly walk requiring both Todoist completion + reflection filled, monthly walk with month-day-1 boundary).
- `tests/test_dashboard.py` *(Phase E, new)* — 19 (paused_summary shapes, github_blob_url, last_7_color rules, scan_reflections, write_css_if_absent, plus four byte-equal snapshot fixtures: empty / partial / full / paused).
- `tests/test_main.py` *(Phase E adds 6)* — dashboard renders ok, skipped flag, dry-run None, render-failure logs without failing run, `Dashboard:` line in LOG, paused state still renders.
- `tests/conftest.py` *(Phase E, new)* — autouse stub for `TodoistCompletionClient` so pre-Phase-E tests don't burn cycles in HTTP retries.

### CI / scheduling
- `.github/workflows/test.yml` — pytest on PRs + pushes to main.
- `.github/workflows/daily.yml` — `cron: "30 21 * * *"` (03:00 IST) + `workflow_dispatch`. Reads `secrets.TODOIST_TOKEN`. Commits cache, LOG.md, and any new reflection stubs.

## What is stubbed / deliberately deferred

- **Module advancement automation.** `state.current_module` advances manually (owner edits state.yaml at module/month boundaries). Same discipline as `state.month`. No engine-driven advancement.
- **`rebuild_cache.py` (Phase F script).** Runtime marker dedup handles cache loss; Phase F's offline script handles the long tail.
- **`dry_run` workflow input.** Local CLI has it. Surfacing as a `workflow_dispatch` input is Phase F.
- **Live-probe of the Todoist v1 completion endpoint shape.** The client tolerates `items` or `results` keys. Before deploy, run a one-shot probe with the real token against the sandbox project and pin the actual shape (Phase F).

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

## Phase E "Done when" gate — VERIFIED ✅

| Probe | Expected | Result |
|---|---|---|
| `python -m src.main --dry-run` | does NOT generate dashboard | ✅ |
| `python -m src.main --skip-dashboard` | `dashboard_status="skipped"`, no docs write | ✅ |
| Real run | `docs/index.html` + `docs/assets/data.json` regenerated; CSS untouched | ✅ |
| Snapshot tests | empty / partial / full / paused all byte-equal | ✅ |
| Render failure | logs WARNING; run exits 0; `dashboard_status="error"` | ✅ |
| Paused state | dashboard still renders; past streaks preserved | ✅ |
| Page weight | ~4.4 KB CSS + ~5.3 KB HTML + ~3 KB JSON ≪ 100 KB | ✅ |
| `TodoistClient` × `TodoistCompletionClient` | private-method intersection empty | ✅ |

## Phase F entry points

Phase F = production readiness + ergonomic polish. **Strict priority order — do not work out of order, items 1–2 are blocking.**

1. **Live-probe `/tasks/completed/by_completion_date`** *(blocking)*. The Phase E client tolerates either `items` or `results` and either `task_id` or `id` against the live shape; until the real shape is verified against the production token, **streak walks may be silently wrong** (the dashboard will render but with stale or zero streaks). Run a one-shot probe against the sandbox project, lock the field names in `TodoistCompletionClient._extract_items`, and remove the tolerance branch.

2. **`rebuild_cache.py`** *(blocking)*. Offline script that reconstructs `.task_cache.json` from project markers — a standalone CLI mirror of `_fetch_marker_ids`. Phase A scaffolded the runtime marker fallback; this is the catastrophic-recovery sibling. Required before any operation that could wipe the local cache.

3. **Synthetic pause smoke test.** Five-minute exercise to surface "passes unit tests but breaks in practice" bugs while the Phase E code is fresh:
   1. Toggle `paused: true`, set `paused_since: <today>`.
   2. `python -m src.main --dry-run --today <today+1>` — confirm SKIP (paused) on all dailies; dashboard render is gated to a real run, so optionally generate against the sandbox cache.
   3. `--dry-run --today <today+2>`, `<today+3>` — same.
   4. Unpause: flip `paused: false`, append `pause_history: [{start: <today>, end: <today+3>, reason: "smoke"}]`, clear `paused_since`.
   5. `--dry-run --today <today+4>` — daily streak should preserve any prior streak, not reset to zero. Last-7-days timeline should show the paused days as gray.
   This isn't an automated test; it's a checklist run against the live state file with `--cache-file .task_cache.sandbox.json` so the production cache stays clean.

4. **`workflow_dispatch` `dry_run` input.** Surface `--dry-run` as a workflow input so the owner can preview a future date from the GitHub UI without checking out locally.

5. **Last-Saturday quadruple-firing UX.** Decide whether `weekly-saturday-deep-block` and/or `weekly-read-real-code` should skip on last-Saturdays so monthly-retrieval + monthly-review don't drown them out.

6. **GitHub Pages enablement.** One-time owner click-through in repo settings (Settings → Pages → Deploy from a branch → main / `/docs`). Documented in README; no code change required.

7. **Holiday week pair-day collision.** `pair_day: thursday` + Thursday holiday silently empties the day. No catch-up logic. Either rotate `pair_day` or add a one-shot override.

### Phase F operating rule (from owner, 2026-05-04)

**No `python -m src.main` invocation against the production Todoist project unless gated by `--dry-run`, a sandbox `--cache-file`, or `--cleanup-project <SANDBOX_ID>`.** This includes smoke tests, sanity checks, and one-off verifications. `--today` freezes the clock but does NOT prevent API writes — it is not a safe substitute. If a real run is genuinely needed, ask the owner first.

## Constraints holding

- Python ≥3.11. Stdlib + `requests`, `PyYAML`, `markdown`, `pytest`. No frameworks, no async, no ORMs.
- One system-clock injection point: `src/clock.py:29`.
- Token never logged. `logging` everywhere; `print` only for CLI table output.
- Daily-run client write-only on task state; idempotency reads permitted; destructive ops on a separate class.
- **Phase E:** read-only completion client is strictly isolated from the write-only daily client. No shared private methods. A regression test enforces this.
- **Phase E:** dashboard render is deterministic — no `datetime.now()`, no random ordering, byte-equal snapshot tests.
- **Phase E:** `docs/assets/style.css` is laid down once and left alone. The owner may hand-edit; the engine never overwrites.
- **Phase E:** pause state never freezes the dashboard. Streak walks treat paused windows as "not counted, not a break."
- Owner TZ everywhere via `Clock(state.timezone)`. UTC only for `created_at` cache stamps.
- Pin to Todoist API v1; paginated list responses follow `next_cursor`.
- Engine reads/writes only `reflections/{weekly,monthly,quarterly,annual}/`. `private/`, `debugging/`, `pairing/` are owner-only.
- `state.current_module` and `state.month` are owner-managed (manual advancement at module/month boundaries). Engine never writes to `state.yaml`.

— end of Phase E —
