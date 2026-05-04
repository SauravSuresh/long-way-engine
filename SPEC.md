# SPEC — *The Long Way* Engine

A GitHub-Actions-driven personal system that turns a 3-year learning syllabus into Todoist tasks, captures reflections as version-controlled markdown, and renders a dashboard showing how the work is going. The repo is the system.

This document is the full design. The work is broken into seven phases (A through G), each ending in a verifiable shippable state.

---

## Goals, in priority order

1. **Don't lie about progress.** A streak that includes days you didn't actually do the work is worse than no streak. Completion state must come from real Todoist data.
2. **Idempotency above all else.** A second run must never duplicate tasks. A failed-and-retried run must never duplicate tasks. Cron and `workflow_dispatch` triggers must produce identical outputs given identical state.
3. **Don't spam the inbox.** Skip rules (Sundays, paused state, completed module tasks) are non-negotiable.
4. **The repo is the system.** State, reflections, cache, dashboard — all committed. The Todoist project and GitHub Pages site are derived views.
5. **Easy to pause, resume, and reshape.** Owner edits `state.yaml`, commits, next run picks up.
6. **Readable code.** Owner is one year into Python at most. No frameworks. Type hints. Short functions. Tests for the load-bearing logic only.

---

## Non-goals

- No web app. No backend server. No login. No multi-user.
- No automatic syllabus parsing beyond a tiny lookup for "current book."
- No LLM-generated content anywhere in the runtime path. Determinism is a feature.
- No editing or completing Todoist tasks from the engine. **Read completion state only.** Never write anything except new tasks.
- No analytics dashboards beyond what's in this spec. Resist scope creep.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│ GitHub repo (public)                                               │
│                                                                    │
│  the-long-way.md           ← syllabus, hand-edited at month       │
│                              boundaries                            │
│                                                                    │
│  state.yaml                ← phase, module, start date, pauses,    │
│                              active branches, manual counters      │
│                                                                    │
│  config.yaml               ← Todoist project ID, label names, TZ,  │
│                              ritual times                          │
│                                                                    │
│  task_templates/           ← parameterized task templates          │
│    daily.yaml                                                      │
│    weekly.yaml                                                     │
│    monthly.yaml                                                    │
│    quarterly.yaml                                                  │
│    practices.yaml                                                  │
│    modules.yaml                                                    │
│    reflections.yaml        ← reflection cadence (Friday, monthly,  │
│                              quarterly, annual)                    │
│                                                                    │
│  reflections/                                                      │
│    weekly/2026-W14.md      ← stub created by engine, filled by     │
│                              owner                                 │
│    monthly/2026-04.md                                              │
│    quarterly/2026-Q2.md                                            │
│    annual/2026.md                                                  │
│    debugging/              ← ad-hoc, owner-created                 │
│    pairing/                ← ad-hoc, owner-created                 │
│    private/                ← gitignored, never read by dashboard   │
│                                                                    │
│  src/                      ← Python package                        │
│    __init__.py                                                     │
│    main.py                 ← entrypoint, orchestrates a run        │
│    syllabus.py             ← lightweight parser for current book   │
│    state.py                ← reads/validates state.yaml            │
│    templates.py            ← loads task_templates/*.yaml           │
│    scheduler.py            ← decides what tasks to create today    │
│    reflections.py          ← creates reflection stubs              │
│    todoist.py              ← API client (write: idempotent create; │
│                              read: completion status only)         │
│    ids.py                  ← deterministic external_id generation  │
│    dashboard.py            ← generates docs/index.html             │
│                                                                    │
│  tests/                    ← pytest, runs on every PR              │
│                                                                    │
│  docs/                     ← GitHub Pages serves this directory    │
│    index.html              ← dashboard, regenerated daily          │
│    assets/                                                         │
│      style.css                                                     │
│      data.json             ← machine-readable run summary          │
│                                                                    │
│  .task_cache.json          ← idempotency cache, committed          │
│  LOG.md                    ← run history, appended each run        │
│  STATUS.md                 ← what's built, what's next              │
│                                                                    │
│  .github/workflows/                                                │
│    daily.yml               ← cron at 05:30 owner-local             │
│    test.yml                ← runs pytest on PRs to main            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                       ↓ Todoist REST API v2          ↓ GH Pages
                  ┌─────────────┐               ┌──────────────┐
                  │   Todoist   │               │  Dashboard   │
                  └─────────────┘               └──────────────┘
```

---

## Data model

### `state.yaml`

```yaml
start_date: 2026-04-01
timezone: Asia/Kolkata
phase: 1
month: 1                       # absolute month from start_date, 1-indexed
current_module: 1              # numbered item in core trunk
active_branches: []            # e.g. ["text-editor-c", "toy-dns-resolver"]
paused: false
manual_counters:               # owner-incremented; dashboard reads these
  anki_card_count: 0           # updated when owner adds cards
  prs_opened: 0                # updated when owner ships a PR
  traces_completed: 0          # updated after each weekly trace
  lineage_detours_done: []     # list of detour IDs, e.g. ["http-1.0", "csp-paper"]
notes: |
  Most recent edit on top.
  2026-04-01: started.
```

Owner is responsible for updating `manual_counters`. The engine never writes to this file. Discipline matters: counters that lie make the dashboard lie.

### `config.yaml`

```yaml
todoist:
  project_id: "1234567890"
  labels:
    daily: "daily-ritual"
    weekly: "weekly-ritual"
    monthly: "monthly-ritual"
    quarterly: "quarterly-ritual"
    practice: "active-practice"
    module: "module-work"
    reflection: "reflection"
ritual_times:
  morning_reading: "06:00"
  anki: "08:30"
  evening_hands_on: "19:00"
  friday_review: "20:00"
  saturday_deep_block: "09:00"
sunday_off: true
dashboard:
  github_username: "your-handle"
  repo_name: "long-way-engine"
```

### `task_templates/*.yaml` shape

```yaml
- id: daily-morning-reading
  title: "Morning reading: {current_book}"
  description: |
    30 min. Paper book, paper notebook, no laptop.
    Today's book: {current_book}.
  due: "today at {ritual_times.morning_reading}"
  labels: [daily-ritual]
  cadence: daily               # daily | weekly | monthly | quarterly | once-per-module
  skip_if: sunday              # null | sunday | paused | module_complete
  variables:
    current_book: derived_from_syllabus

- id: weekly-friday-review
  title: "Friday review: 20-min retrieval"
  description: |
    Without looking at your notes, write down the 3 most important
    things you learned this week. Then compare to your notes. The gap
    is the diagnostic.
  due: "this Friday at {ritual_times.friday_review}"
  labels: [weekly-ritual]
  cadence: weekly
  day_of_week: friday
  reflection:
    create_stub: true
    stub_path: "reflections/weekly/{iso_year}-W{iso_week:02d}.md"
    template: weekly_review_template
```

The `reflection.create_stub: true` flag is the bridge to the reflections subsystem — see below.

### `reflections/` directory

Every reflection cadence has a directory and a markdown template. When a reflection-emitting task is created, the engine *also* creates a stub markdown file with the template, ready for the owner to fill in.

Stub naming uses ISO conventions for sortability:

- `reflections/weekly/2026-W14.md` (ISO week)
- `reflections/monthly/2026-04.md`
- `reflections/quarterly/2026-Q2.md`
- `reflections/annual/2026.md`

Each stub starts with frontmatter the dashboard reads:

```markdown
---
type: weekly
date: 2026-04-03
iso_week: 2026-W14
status: stub
word_count: 0
---

# Weekly review — 2026-W14

## Three things I learned this week
*(Write without looking at notes. Compare after.)*

1.
2.
3.

## What's still fuzzy

## Anki cards added this week
```

The dashboard reads frontmatter to determine `status: stub | filled` and counts words. A stub that has been edited becomes `filled` automatically — see `reflections.py` for the heuristic (word count > template baseline by some threshold). Owner can also manually set `status: filled` in frontmatter to force it.

### `.task_cache.json`

```json
{
  "a3f2b1c4d5e6f7a8": {
    "todoist_task_id": "8901234567",
    "created_at": "2026-04-15T05:30:12+05:30",
    "template_id": "daily-anki",
    "due_date": "2026-04-15"
  }
}
```

Pruned of entries older than 60 days at the end of each run. The content marker (see Idempotency below) is the source of truth; the cache is the fast path.

### `LOG.md`

Appended once per run:

```markdown
## 2026-04-15 05:30 IST
- Created: 5 tasks (3 daily, 1 weekly Friday review, 1 reflection stub)
- Skipped: 0 (cache hits)
- Errors: 0
- Reflection stubs created: reflections/weekly/2026-W14.md
- Dashboard regenerated.
```

---

## Idempotency

### External ID

```
external_id = sha256(template_id + "|" + due_date_iso)[:16]
```

Same template + same due date = same ID. Two runs same day, same template → same ID → no duplicate task.

### Two layers of dedup

1. **Cache file (fast path).** Before creating, check `.task_cache.json`. If `external_id` is present, skip without an API call.
2. **Content marker (correctness).** Append `<!--LW:{external_id}-->` to every task description. Invisible in the Todoist UI for descriptions. If the cache is ever lost or corrupted, `rebuild_cache.py` reconstructs by listing project tasks and parsing markers.

The cache makes runs fast; the marker makes them safe. Both must exist.

### Once-per-module tasks

Module-onboarding tasks (e.g. "Module 1: Python Basics — read syllabus section, set up boot.dev path") have `cadence: once-per-module` and a different ID scheme:

```
external_id = sha256(template_id + "|module:" + module_number)[:16]
```

So advancing `current_module: 1 → 2` causes the next run to create module 2's onboarding task once, even though no date changed.

---

## Read-only completion API

The streaks dashboard requires knowing whether tasks were completed. This is the *only* read interaction the engine has with Todoist, and it must be strictly separated from the write path:

- `todoist.py` exposes `create_task_idempotent(...)` (write) and `get_completion_status(task_ids: list[str]) -> dict[str, bool]` (read).
- The read function uses the Todoist `/tasks/completed` and `/tasks` endpoints to determine whether each ID is in active tasks (not done), in completed tasks (done), or neither (deleted/missing).
- The read function never modifies anything. Code review check: any PR adding a `POST`, `PATCH`, or `DELETE` call to the completion code path must be rejected.
- Read results are cached in `.completion_cache.json` for 6 hours to stay under rate limits.

---

## The scheduler

Single GitHub Actions cron, `daily.yml`, at 05:30 owner-local. The job:

1. Checks out repo with write permission (it commits cache and dashboard updates back).
2. Loads `state.yaml`, `config.yaml`, all templates.
3. Computes `today` in owner's TZ.
4. If `paused: true`: log, skip task creation, *but still regenerate dashboard*. Pause should not freeze the dashboard.
5. For each template, ask `should_create_today(template, today, state) -> bool`:
   - **daily**: yes unless `skip_if: sunday` and today is Sunday, or `paused`.
   - **weekly**: yes if today's day-of-week matches `day_of_week`.
   - **monthly**: yes if today matches `day_of_month` rule (`1`, `last-saturday`, etc.).
   - **quarterly**: yes if today is the first day of a quarter (Jan 1, Apr 1, Jul 1, Oct 1) or matches a configured offset.
   - **once-per-module**: yes if `current_module` matches and task not in cache by module-keyed ID.
6. For each yes:
   - Compute external_id.
   - Check cache and content-marker. Skip if dedup hit.
   - Resolve variables (today's book, current module name, etc.).
   - Create Todoist task with marker.
   - If template has `reflection.create_stub: true`, also create the stub markdown file with the template, *unless the file already exists* (don't clobber owner's work).
   - Add to cache.
7. After all tasks: read completion status of recent tasks (last 30 days) for dashboard.
8. Regenerate `docs/index.html` from state, manual_counters, completion data, and reflection directory listing.
9. Append summary to `LOG.md`.
10. Commit cache, log, dashboard, and any new reflection stubs in a single commit titled `chore: daily run YYYY-MM-DD`.
11. Push.

---

## Dashboard

A static HTML page generated each run. GitHub Pages serves `docs/`. The dashboard has no JavaScript framework — vanilla HTML/CSS/JS only. Read the `data.json` file it ships alongside if you need to.

### Sections

1. **Header.** Days into the plan (computed: `today - start_date`). Current phase and module. "On track" / "paused" status. Total months / 36.
2. **Streaks.** Three streak counters:
   - Daily ritual streak (consecutive non-Sunday days where `daily-anki` and `daily-morning-reading` were both completed).
   - Weekly review streak (consecutive Fridays with `weekly-friday-review` completed AND a filled weekly reflection).
   - Monthly post streak (consecutive months with the monthly blog post task completed).
3. **Phase / module progress bar.** A horizontal bar with phase 1–4 boundaries, current month marker, current module label.
4. **Reflection log.** Reverse-chronological list of all reflection files. Each row: type (weekly/monthly/quarterly/annual), date, word count, status (stub/filled), link to the file on GitHub. Quarterly and annual rows visually distinct (highlighted).
5. **Active practice tracker.** Four counters from `manual_counters` and computed values:
   - Traces completed (manual)
   - PRs opened (manual)
   - Lineage detours done (manual, listed by name)
   - Code-reading sessions (count of `weekly-saturday-read` completions, computed from Todoist)
6. **Books.** Reading list per phase, parsed from syllabus. Three states per book: not started / current / done. State is hand-edited in `state.yaml` under `books_state`. The dashboard renders the current phase's reading list with state-based styling.
7. **Last 7 days timeline.** Tiny grid: each day a square, color-coded green (completed all daily rituals) / yellow (partial) / gray (Sunday/paused) / red (missed). At-a-glance recent history.
8. **Footer.** Last run timestamp, link to the LOG.md, link to the repo.

### Visual style

- Single-column, ~700px max width, generous whitespace.
- System font stack. No web fonts.
- Subtle palette: light background, high-contrast text. Greens for completion, soft red for misses, gray for skipped/paused.
- Print-friendly (the owner may print the quarterly synthesis page).
- No analytics, no tracking pixels, no external resources.
- Built such that loading the page works offline once cached.

### `docs/assets/data.json`

The dashboard's underlying data, also useful for debugging and external scripts:

```json
{
  "generated_at": "2026-04-15T05:32:00+05:30",
  "days_in": 14,
  "phase": 1,
  "month": 1,
  "current_module": {"number": 1, "title": "Python Basics"},
  "paused": false,
  "streaks": {
    "daily": 12,
    "weekly_review": 2,
    "monthly_post": 0
  },
  "reflections": [
    {"type": "weekly", "date": "2026-04-10", "path": "reflections/weekly/2026-W14.md", "word_count": 320, "status": "filled"},
    {"type": "weekly", "date": "2026-04-03", "path": "reflections/weekly/2026-W13.md", "word_count": 50, "status": "stub"}
  ],
  "manual_counters": {...},
  "last_7_days": [
    {"date": "2026-04-15", "status": "completed"},
    {"date": "2026-04-14", "status": "partial"},
    ...
  ]
}
```

### Reflections directory privacy

`reflections/private/` is in `.gitignore`. The dashboard does not list its contents and does not count its files. Owner can move any reflection there to keep it off the public site.

---

## Failure modes

| Failure | Behavior |
|---------|----------|
| Todoist API 5xx | Retry 3x with exponential backoff. If still failing, exit non-zero, do not commit cache. Next run retries. |
| Todoist API 401 | Log clear error, exit non-zero. Owner gets GH email. |
| `state.yaml` malformed | Validate on startup, exit with line number. |
| Template missing variable | Skip *that template*, log warning, continue. Don't fail run. |
| Cache file corrupted | Log warning, treat as empty, continue. Marker dedup prevents duplicates. |
| Reflection stub file collision | If file exists, do not overwrite. Just create the Todoist task. |
| GH Actions runner clock skew | Always use owner TZ from `config.yaml`, never runner-local. |
| Dashboard generation fails | Log error, do *not* fail the whole run — task creation succeeded; dashboard can wait. Surface in next run. |
| Push fails (e.g. concurrent edit) | Pull, retry once. If still failing, exit non-zero. |

---

## Phased build plan

**Build in this order. Each phase ends in a verifiable shippable state. Do not skip ahead. Do not start the next phase until the previous one is verified working in real Todoist.**

### Phase A — Walking skeleton *(target: 1–2 sessions)*

Get a single end-to-end happy path working with two daily tasks.

- Repo structure scaffolded, `pyproject.toml` or `requirements.txt`.
- `state.yaml`, `config.yaml` with realistic values.
- `task_templates/daily.yaml` with two templates (morning reading, Anki).
- `src/`: `main.py`, `state.py`, `templates.py`, `todoist.py`, `ids.py`. Hardcoded scheduler logic ("if it's a daily and not Sunday, create").
- Idempotent task creation: cache + content marker.
- `.github/workflows/daily.yml` — cron + `workflow_dispatch`.
- `.github/workflows/test.yml` — runs pytest on PRs.
- Tests: `ids.py` deterministic output; `todoist.py` idempotency with mocked HTTP.
- `STATUS.md` describing what's done and next.

**Done when:** running the workflow twice on the same day creates exactly 2 tasks total. Cache file shows up as a commit.

### Phase B — All ritual cadences *(target: 2–3 sessions)*

Add weekly, monthly, quarterly templates and the proper scheduler.

- `task_templates/weekly.yaml`, `monthly.yaml`, `quarterly.yaml` populated from the syllabus's ritual section.
- `src/scheduler.py` extracted: `should_create_today()` with cadence dispatch.
- Day-of-week, day-of-month, last-Saturday-of-month, first-of-quarter rules.
- `paused: true` short-circuits task creation.
- Sunday-off honored across all daily tasks.
- Tests covering: Sunday skip, last-Saturday calculation, quarter boundaries, paused state, ISO week edge cases (year boundary).

**Done when:** running with synthetic `today=Friday` produces the Friday review; `today=Sunday` produces zero daily tasks; `today=last-Saturday-of-month` produces the monthly retrieval task; `paused: true` produces zero tasks of any kind.

### Phase C — Reflections subsystem *(target: 2 sessions)*

Bridge tasks to version-controlled markdown reflections.

- `reflections/` directory tree with `.gitkeep` files.
- Template strings for weekly / monthly / quarterly / annual reflection stubs (the markdown skeletons described above, with frontmatter).
- `src/reflections.py` — given a template and a date, write the stub file at the right path *if it doesn't already exist*. Never overwrite.
- Templates with `reflection.create_stub: true` trigger stub creation alongside Todoist task creation.
- Stub frontmatter: `type`, `date`, `iso_week` (or month/quarter equivalent), `status: stub`, `word_count: 0`.
- A small utility `update_reflection_metadata.py` (or a step in `main.py`) that updates `word_count` and `status` for all reflections each run, by reading current word counts.
- `reflections/private/` added to `.gitignore`.
- Tests: stub creation idempotent (no overwrite), frontmatter parsing, word count updating.
- `README.md` for `reflections/` explaining: don't rename files, fill in below frontmatter, move to `private/` to hide.

**Done when:** Friday's run creates `reflections/weekly/2026-W14.md` as a stub *and* the Todoist task. Editing the file and re-running updates `word_count` and toggles `status` to `filled`. Re-running with the file already present does not clobber it.

### Phase D — Active practices and module work *(target: 2 sessions)*

Practices and the module trunk.

- `task_templates/practices.yaml` with weekly / monthly / quarterly active practices: trace one thing (Sunday), read real code (Saturday), open a PR (monthly), build the thing under the thing (quarterly), debug deliberately (continuous reminder, not a task).
- `task_templates/modules.yaml` with one entry per syllabus module (1 through 23). Each has: `module_number`, `title`, `phase`, `onboarding_task` (created once when this module becomes current), `lineage_detour` (optional, with own `once-per-module` task).
- `src/syllabus.py` — minimal regex extractor for the "Phase X reading" sections, used to populate `{current_book}` for the morning reading template based on the current `month`.
- Module advancement: editing `state.yaml` `current_module: 1 → 2` causes the next run to create module 2's onboarding task. Detect via cache miss on the module-keyed external ID.
- Lineage detour tasks: created once when `current_module` matches, deduped by module-keyed ID.
- Tests: module advancement creates exactly one onboarding task; advancing again before completion does not duplicate; `{current_book}` resolves correctly across all four phases.

**Done when:** running with `current_module: 1` creates the module 1 onboarding task. Editing to `current_module: 2` and re-running creates module 2's task and *does not recreate* module 1's. Morning reading task title shows "Computer Systems: A Programmer's Perspective" in month 1, "Computer Networking: A Top-Down Approach" in month 7 (per the syllabus reading schedule).

### Phase E — Read-only completion + dashboard *(target: 3–4 sessions)*

The dashboard, with real completion data.

- `src/todoist.py` extended with `get_completion_status(task_ids)` — strictly read-only, well-tested, well-isolated.
- `.completion_cache.json` for 6-hour caching of completion lookups.
- `src/dashboard.py` — pure function from `(state, completion_data, reflection_listing) -> html_string`.
- `docs/index.html` and `docs/assets/style.css` and `docs/assets/data.json` written each run.
- All seven dashboard sections implemented (header, streaks, progress bar, reflections log, practice tracker, books, last 7 days timeline, footer).
- Books reading state: `books_state` in `state.yaml`, hand-edited.
- Streak calculations:
  - Daily streak: walk back from today, counting non-Sunday days where both `daily-anki` and `daily-morning-reading` external_ids show as completed in Todoist.
  - Weekly review streak: walk back week-by-week, requiring both Todoist completion AND `status: filled` on the corresponding reflection file.
  - Monthly post streak: walk back month-by-month, Todoist completion of the monthly post task.
- GH Actions config: enable Pages on `docs/` (do this in repo settings; instructions in README).
- Tests: streak edge cases (broken streak, Sunday in middle, paused period), HTML generation snapshot tests for empty / partial / full state.

**Done when:** dashboard renders at `https://username.github.io/long-way-engine/`. Streaks reflect actual completion. Reflection log lists files in `reflections/` with correct word counts. Books section shows the current phase's reading list. Page loads under 1 second, weighs under 100KB total.

### Phase F — Polish and resilience *(target: 1–2 sessions)*

Sand the rough edges.

- `dry_run` boolean input on `workflow_dispatch` — logs all decisions without creating tasks or writing files.
- `rebuild_cache.py` — one-shot script to reconstruct `.task_cache.json` from Todoist by parsing content markers. Documented in README.
- `LOG.md` formatting cleaned up; pruned to last 90 days.
- Owner-facing `README.md` covering: setup (Todoist token, project ID, Pages enablement), pause flow, module advancement, adding/editing templates, recovering from cache loss, archiving a year.
- A `bootstrap.py` for first-time setup: prompts for Todoist token, creates the project (or asks for the ID), generates initial `state.yaml` and `config.yaml`. Single one-shot script.
- All errors produce GitHub annotations (`::error::`) so they surface on the Actions UI, not just in logs.

**Done when:** a fresh-eyed reader could clone the repo, run bootstrap, and have a working system in 15 minutes.

### Phase G — Year-boundary tooling *(target: 1 session, deferred until needed)*

You won't need this for ~12 months. Designing it now so it's not a refactor later.

- `src/archive.py` — at year boundary, owner runs a script that:
  - Moves the year's reflections into `reflections/archive/<year>/` keeping structure.
  - Compiles a `reflections/archive/<year>/index.md` summary with links to all reflections, word counts, key themes (manual section the owner fills).
  - Generates a year-in-review snapshot of the dashboard as `docs/archive/<year>.html`.
- This is *deliberately* a manual command, not automated. The end-of-year review is sacred (per the syllabus); it shouldn't be auto-anything.

**Done when:** owner runs `python -m src.archive 2026` at end of year and gets a clean archive without breaking the live dashboard.

---

## Constraints that bind every phase

- **Python 3.11+, stdlib + `requests` + `pyyaml` + `pytest` + `markdown` (for word count of rendered text). No frameworks, no async, no ORMs.**
- **No LLMs at runtime.** Every decision is deterministic.
- **Owner TZ everywhere.** Use `zoneinfo` from stdlib. Never `datetime.now()` without a tz; never the runner's local time.
- **Token never logged.** Redact in any debug output.
- **No `print` for status. Use `logging`.** Workflow logs are the operator UI.
- **Type hints everywhere. Functions short. Modules match the architecture diagram.**
- **Test the load-bearing logic. Don't aim for coverage; aim for confidence.**
  - `ids.py`: determinism, collision properties.
  - `todoist.py`: idempotency, retry behavior, *strict separation of read and write paths*.
  - `scheduler.py`: every cadence, every skip rule, time edge cases.
  - `reflections.py`: never-overwrite invariant, frontmatter parsing.
  - `dashboard.py`: snapshot tests on representative state.
- **Code review checklist for every PR:** Does this PR add any write call (POST/PATCH/DELETE/POST-completed) outside `create_task_idempotent`? If yes, reject.

---

## Open questions for the owner *(Claude Code should ask these before Phase A)*

1. **Todoist project.** Will it already exist when Phase A starts, or should `bootstrap.py` (Phase F) create it? *(Suggest: create manually for Phase A, automate later.)*
2. **GitHub Pages.** Confirm the repo will be public. Note that `state.yaml`, reflections, and `LOG.md` will all be world-readable.
3. **Cron time.** 05:30 Asia/Kolkata — confirm.
4. **Ritual times.** Defaults in spec are placeholders. Confirm preferred times for morning reading, Anki, evening hands-on, Friday review.
5. **Friday review checklist.** Should the weekly reflection stub include a fillable checklist with specific prompts (3 things learned, what's still fuzzy, Anki cards added), or just a blank prompt? *(Suggest: checklist with prompts, matching the syllabus.)*
6. **Module advancement signal.** When a module is "done," does the owner just edit `current_module` in state, or do we want an explicit `completed_modules: [1, 2, 3]` list to make the dashboard accurate? *(Suggest: completed_modules list. Cleaner state.)*
7. **Books state granularity.** Per-book state (not started / current / done), or finer (chapter-level)? *(Suggest: per-book. Avoid template explosion.)*

These are tractable; Claude Code should bundle them and ask before starting Phase A.
