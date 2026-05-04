# STATUS

Phase A — walking skeleton — complete in code. Awaiting the manual verification gate (real Todoist run) for the final sign-off.

## What works

### Code
- `src/ids.py` — deterministic SHA256-based `external_id(template_id, due_date)` returning 16 hex chars. Includes `module_external_id(template_id, module_number)` shape for Phase D.
- `src/cache.py` — JSON cache load/save with atomic write, corruption tolerance, and 60-day pruning.
- `src/config.py` — loads `config.yaml` and the Todoist token from `.env` (10-line stdlib parser) or `TODOIST_TOKEN` env var. `Config.__repr__` redacts the token; `TokenRedactingFilter` strips it from any log record as defense in depth.
- `src/state.py` — loads and validates `state.yaml`. Required keys + ZoneInfo + date checking. Dataclass scaffolds Phase B–F fields (`completed_modules`, `paused`, `manual_counters`, etc.) so the schema is stable.
- `src/templates.py` — loads `task_templates/*.yaml` and resolves `{current_book}` and `{ritual_times.<key>}` placeholders. Missing variables warn and skip the affected template, never crash the run.
- `src/scheduler.py` — Phase A logic: `cadence: daily` + `skip_if: sunday` + `config.sunday_off`. Other cadences raise `NotImplementedError` so Phase B drift fails loudly.
- `src/todoist.py` — write-only `TodoistClient.create_task_idempotent`. Cache hit = zero API calls; cache miss = one POST with `<!--LW:{id}-->` appended to description. Retries 3× on 5xx with exponential backoff, raises immediately on 401, raises on other 4xx without retry. Module docstring + a regression test enforce that no `get`/`patch`/`delete`/`complete`/`update` method exists on the class until Phase E intentionally adds the read API.
- `src/main.py` — orchestrates one run: load config + state + templates → today in owner TZ → for each template `should_create_today`? → resolve variables → check cache → create → update cache → prune → save → append `LOG.md`. Logging uses stdlib `logging` with the redacting filter installed at root.

### Configuration
- `state.yaml` — `start_date: 2026-05-04`, timezone `Asia/Kolkata`, current_book set to "Computer Systems: A Programmer's Perspective".
- `config.yaml` — placeholder `project_id` and `github_username`; ritual times configurable; full label set.
- `.env.example` — `TODOIST_TOKEN=` placeholder. `.env` is gitignored.
- `task_templates/daily.yaml` — two entries: `daily-morning-reading` and `daily-anki`. Both `cadence: daily`, `skip_if: sunday`, label `daily-ritual`.

### Tests (50 passing, all stdlib + mocked HTTP)
- `tests/test_ids.py` — determinism, distinctness across template/date, 16-char hex shape (5 tests).
- `tests/test_cache.py` — round-trip, missing/corrupt/non-object handling, prune drops old keeps recent, prune keeps unparseable created_at (7 tests).
- `tests/test_config.py` — `.env` parser edge cases, env-var fallback, missing-token raises, `__repr__` redacts, `TokenRedactingFilter` strips from log records (9 tests).
- `tests/test_state.py` — happy path, missing keys exit, bad timezone exits, bad date exits (4 tests).
- `tests/test_templates.py` — load directory, resolve `{current_book}` and `{ritual_times.X}`, missing variable returns None + warns (4 tests).
- `tests/test_scheduler.py` — Sunday + skip = False, Monday = True, no-skip Sunday = True, `sunday_off=False` overrides, weekly raises NotImplementedError (5 tests).
- `tests/test_todoist.py` — marker format, append-marker shapes, cache hit = 0 calls, cache miss = 1 POST with marker in body, marker regex extracts id, 5xx retries 3× then raises, 5xx-then-200 succeeds, 401 immediate raise, other 4xx no retry, no GET/PATCH/DELETE methods on client, token never appears in log records (12 tests).
- `tests/test_main.py` — end-to-end with FakeClient: Monday creates 2, second run same day creates 0, Sunday creates 0, `LOG.md` appends without clobber (4 tests).

### CI / scheduling
- `.github/workflows/test.yml` — runs `pytest -q` on PRs to main and pushes to main, Python 3.11.
- `.github/workflows/daily.yml` — `cron: "30 21 * * *"` (= 03:00 next-day Asia/Kolkata) + `workflow_dispatch`. Permissions `contents: write`. Reads `secrets.TODOIST_TOKEN`. Commits `.task_cache.json` and `LOG.md` if changed, push, with concurrency group `daily-run`.

## What is stubbed / deliberately deferred

- **Read-side Todoist API.** `get_completion_status` not present anywhere; module docstring reserves the name and a test enforces absence. Phase E owns it.
- **Reflection stubs.** Templates have no `reflection.create_stub` flag yet. Phase C wires `src/reflections.py` and the `reflections/` directory tree.
- **Weekly / monthly / quarterly cadences.** `scheduler.should_create_today` raises `NotImplementedError` for anything other than `daily`. Phase B replaces this with a cadence-dispatch table.
- **`paused` short-circuit.** Field exists in `state.yaml` and `State` dataclass but is not consulted by the scheduler. Phase B wires it.
- **Module / once-per-module cadence.** `module_external_id` exists in `src/ids.py` for Phase D; no template uses it yet.
- **Syllabus parser.** `current_book` is hardcoded in `state.yaml`. Phase D adds `src/syllabus.py` and replaces the field with a parsed lookup keyed off `state.month`.
- **Dashboard.** No `docs/`, no `src/dashboard.py`, no `data.json`. Phase E owns the entire dashboard.
- **`rebuild_cache.py`.** The content marker is written into every task description, but the cache is never reconstructed from it at runtime — Phase A is write-only. Phase F adds the rebuild script that issues read calls.
- **Template count.** Only two templates (morning reading, Anki). The full ritual stack (evening hands-on, Friday review, Saturday deep block, monthly post, monthly retrieval, quarterly synthesis, annual review) lands across Phases B–C.

## Phase A "Done when" gate — verification checklist

The code is ready. To confirm Phase A actually works against real Todoist:

1. **Set Todoist project ID.** Edit `config.yaml`: replace `REPLACE_WITH_TODOIST_PROJECT_ID` with the real "Long Way" project ID. Replace `REPLACE_WITH_GH_HANDLE` and confirm `repo_name`.
2. **Set the Todoist token locally.** `cp .env.example .env && echo "TODOIST_TOKEN=..." > .env`. Optionally run `python -m src.main` once locally — should create 2 tasks if today is not Sunday, 0 if it is.
3. **Set the Todoist token as a GitHub secret.** Repo settings → Secrets and variables → Actions → New repository secret named `TODOIST_TOKEN`.
4. **Push the branch.** All pytest jobs should go green.
5. **Trigger `daily.yml` manually** (Actions tab → daily → Run workflow). Confirm:
   - 2 tasks appear in the Todoist "Long Way" project, dated today, label `daily-ritual`. (0 if today is Sunday.)
   - The workflow commits `.task_cache.json` and `LOG.md` to the repo. The cache has 2 entries.
6. **Trigger `daily.yml` again the same day.** Confirm 0 new tasks created. Cache unchanged. `LOG.md` has a second entry showing `Created: 0, Skipped (cache hit): 2`.

If all six pass, Phase A is verified and Phase B can begin.

## Next session — Phase B entry points

Phase B = "all ritual cadences." Touch points:

- `src/scheduler.py`: replace the `cadence == "daily"` branch with a dispatch over `daily | weekly | monthly | quarterly`. Add `paused: true` short-circuit at the top.
- New: `task_templates/weekly.yaml`, `monthly.yaml`, `quarterly.yaml` populated from `the-long-way.md` rituals (Friday review, Saturday deep block, monthly post + retrieval, quarterly synthesis, annual review).
- New tests: Sunday across all dailies, last-Saturday-of-month, first-day-of-quarter, ISO week year-boundary edge case, paused → zero tasks of any kind.
- The existing daily templates and `daily.yaml` workflow do not need to change.

## Constraints holding

- Python ≥3.11. Stdlib + `requests`, `PyYAML`, `markdown`, `pytest`. No frameworks, no async, no ORMs.
- All `datetime.now()` calls use `state.timezone`; the runner's local time is never trusted (only UTC is used for `created_at` timestamps in the cache, which are TZ-aware ISO strings).
- Token never logged. `logging` everywhere; no `print` for status.
- Read/write separation in `src/todoist.py` enforced by both docstring and a regression test.

— end of Phase A —
