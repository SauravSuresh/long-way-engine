# Forking long-way-engine for your own learning plan

This guide walks you from a fresh fork to a daily-running engine that
creates Todoist tasks against your own curriculum and publishes a
progress dashboard.

**The recommended way to design your curriculum is the AI-agent
interview in [`AGENTS.md`](../AGENTS.md)**. That file is the spec
for how a well-formed fork should be written — schema, validation
rules, anti-patterns, and a 7-step interview protocol any capable
AI agent (Claude, Cursor, Codex, etc.) can run with you to produce
a complete `curriculum/` bundle. The "Step 4 — Pick or build a
curriculum" section below covers both that path and the
copy-an-example shortcut.

## What you'll end up with

- A GitHub Action that runs every morning and creates today's tasks
  in your Todoist (deduped — same task never appears twice).
- A static HTML dashboard at `https://<you>.github.io/<repo>/` that
  shows your current phase / month / module, streaks, books read,
  and reflection log.
- Reflection markdown stubs auto-generated for weekly / monthly /
  quarterly / annual rituals.
- All of it driven by YAML files you edit in `curriculum/` — no
  Python code changes required.

## Prerequisites

- A Todoist account (free works) and a personal API token.
- A GitHub account.
- Python 3.11 or newer locally (only for testing — production runs
  in GitHub Actions).

## Step 1 — Fork the repo

Use GitHub's "Fork" button on https://github.com/SauravSuresh/long-way-engine.
Clone your fork:

```bash
git clone https://github.com/<your-username>/long-way-engine.git
cd long-way-engine
```

## Step 2 — Local Python setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Step 3 — Todoist setup

1. Create a Todoist project for your engine's output. The dashboard
   reads completion status from this project only, so keep it
   separate from your everyday tasks. Note the project's ID — it
   appears in the URL when you open the project in Todoist
   (`todoist.com/showProject?id=XXXX`).
2. Get a personal API token at
   https://todoist.com/app/settings/integrations/developer.
3. Create a local `.env` file (don't commit it):

```bash
echo "TODOIST_TOKEN=your-token-here" > .env
```

## Step 4 — Design your curriculum

Two paths. **Path A is the recommended one** unless you already have
a curriculum in mind and just want to type it in.

### Path A — AI-agent interview (recommended)

[`AGENTS.md`](../AGENTS.md) is the canonical spec for how a fork's
`curriculum/` should be written. Hand it to an AI agent and have the
agent run the 7-step interview with you:

1. Open the cloned repo in your AI tool of choice. Claude Code,
   Cursor, Codex, Aider — anything that can read files in the repo.
2. Send the agent this prompt (or similar):

   > Read `AGENTS.md` end-to-end. Then run the 7-step interview
   > described in section 5 with me to build my curriculum.
   > Write the resulting YAML files under `curriculum/`. After the
   > interview, run the validator to confirm everything passes.

3. Answer the agent's questions, roughly in this order:
   - **Goal & duration.** What do you want to be able to do, by when?
     Concrete capability ("ship a production ML model"), not vague
     understanding ("learn ML"). Pin a month count.
   - **Phase split.** 2–4 phases. Each phase ends in a demonstrable
     capability.
   - **Books / primary resources per month.** One primary per month,
     usually a book or course. Carry-forward is fine (one long book
     can span many months).
   - **Modules.** 2–8 per phase. Discrete units you advance through
     one at a time.
   - **Rituals.** Daily / weekly / monthly habits the engine
     enforces. The agent will insist on two daily defaults regardless
     of your domain:
     - **Spaced-repetition review (Anki or similar)** — 10–15 min/day.
       Non-negotiable. Long-horizon learning without SRS loses ~80% of
       what you covered inside a month. Every curriculum the agent
       generates includes this ritual; you can adjust the time slot
       or swap Anki for another SRS tool, but the cadence stays.
     - **Morning study** — ~30 min/day with the current book.
     Everything else (evening hands-on, weekly retrievals, monthly
     writeups, deep blocks, quarterly synthesis) is recommended but
     adjustable to your life.
   - **Practices.** Optional weekly skill drills outside the
     routine.
4. The agent writes every YAML file. Validator runs at the end.
5. Spot-check the output. If anything feels wrong, push back — the
   agent can revise.

This is the path that produces the best curriculum because the
interview forces you to make every fuzzy intention concrete before
the engine starts running it. About 30 minutes of work.

### Path B — Copy an example and edit

If you want to skip the interview, just copy one of the starter
bundles:

```bash
rm -rf curriculum
cp -r examples/ml-engineer-12mo curriculum
# or:
cp -r examples/frontend-craft-6mo curriculum
# or:
cp -r examples/programmer-to-neuroscience-12mo curriculum
```

Edit the copied files to your liking. Use [`AGENTS.md`](../AGENTS.md)
as the schema reference when you don't know what a field means. The
validator (Step 7) runs at startup and tells you if anything is
malformed.

### Either path: end state

By the end of this step you should have these files in `curriculum/`:

```
curriculum/
├── syllabus.yaml             # phases, books, modules
├── manifest.yaml             # required ritual_times
├── modules.yaml              # one onboarding task per module
├── rituals/
│   ├── daily.yaml
│   ├── weekly.yaml           # optional, but recommended
│   ├── monthly.yaml          # optional
│   └── ...                   # quarterly, annual, practices
└── reflection_templates/     # optional but recommended
    ├── weekly.md
    └── ...
```

## Step 5 — Wire `config.yaml`

Edit `config.yaml`:

```yaml
todoist:
  project_id: "YOUR_TODOIST_PROJECT_ID"      # from Step 3
  labels:                                     # optional Todoist labels
    daily: "daily-ritual"
    weekly: "weekly-ritual"
    monthly: "monthly-ritual"
    practice: "active-practice"
    module: "module-work"
    reflection: "reflection"

# Times of day for ritual templates. Keys must match what your
# curriculum/manifest.yaml lists under `ritual_times_required`.
ritual_times:
  morning_reading: "06:00"
  evening_hands_on: "19:00"
  # ... add whatever slots your curriculum needs

# Optional: which weekday counts as your "pair-with-someone" day.
# Templates with `skip_if: [pair_day]` won't fire on this day.
pair_day: thursday

# Whether Sunday is a rest day (every cadence skips).
sunday_off: true

dashboard:
  github_username: "YOUR_GITHUB_USERNAME"
  repo_name: "long-way-engine"               # or whatever you renamed the fork

# Points at the active curriculum bundle. Default is `curriculum`.
curriculum_dir: curriculum
```

## Step 6 — Initialize `state.yaml`

Edit `state.yaml` to mark day one:

```yaml
start_date: 2026-06-01           # today, in YYYY-MM-DD
timezone: "Asia/Kolkata"          # your tz, used by daily cron
phase: 1
month: 1
current_module: 1
current_book: ""                  # leave empty; engine fills from syllabus
completed_modules: []
active_branches: []
paused: false

# Parallel always-on surfaces (courses, certs, branches, detours).
# Distinct from modules — modules are the linear spine that
# advances one number at a time, learning_tracks are things that
# run in parallel with the spine across months. Categories and
# item names are arbitrary; the engine never validates them, so a
# typo produces a silent extra category at first render.
#
# Examples:
#   learning_tracks:
#     Courses:
#       "boot.dev backend path": current
#     Certifications:
#       "LFCS": not_started
#     Active branches:
#       "Text editor in C": current
#
# Valid leaf states: not_started | current | done. Leave empty if
# nothing parallel is in flight at day one.
learning_tracks: {}

manual_counters:
  anki_card_count: 0
  prs_opened: 0
  traces_completed: 0
  lineage_detours_done: []

notes: |
  Day 1 — starting.
```

## Step 7 — Dry-run

```bash
python -m src.main --dry-run --today $(date +%Y-%m-%d)
```

This:
- Validates your curriculum bundle (10 checks; aggregated error if
  any fail).
- Shows every template, whether it would fire today, and the
  resolved title / description / due time.
- Touches no external services. Nothing gets written to Todoist.

If you see `CurriculumError`, read the message — it tells you which
file, which field, and what's wrong. Common issues:

- `primary_book_by_month[X] = '...' has no matching books[].title`
  → typo in one or the other; titles must match exactly.
- `manifest requires ritual_time 'foo' but config has no such key`
  → add the time to `config.yaml`'s `ritual_times`.
- `module N has no once-per-module task in modules.yaml` → every
  syllabus module needs an onboarding task.

Once `--dry-run` looks right, do a live run:

```bash
python -m src.main --today $(date +%Y-%m-%d)
```

You'll see tasks appear in your Todoist project. Run it again
immediately — nothing duplicates (the cache file `.task_cache.json`
remembers what's already been created).

## Step 8 — GitHub Actions for the daily cron

The repo already ships `.github/workflows/daily.yml`. To activate:

1. **Add the secret.** GitHub repo → Settings → Secrets and variables
   → Actions → New repository secret. Name: `TODOIST_TOKEN`. Value:
   your Todoist token.
2. **Adjust the schedule** (optional). The cron expression at the
   top of `daily.yml` runs at 03:00 Asia/Kolkata (21:30 UTC). Edit
   to fit your timezone if you want a different morning time.
3. **Commit** any curriculum edits and push to your fork's `main`
   branch. The cron will fire on its schedule.

You can also trigger manually: repo → Actions → "Daily" → Run
workflow.

## Step 9 — GitHub Pages for the dashboard (optional)

The daily cron also regenerates `docs/index.html`. To make it public:

GitHub repo → Settings → Pages → Source: **Deploy from a branch** →
Branch: `main` / folder: `/docs` → Save.

After the next cron run, your dashboard is at
`https://<your-username>.github.io/<repo-name>/`.

## Step 10 — Maintenance

After fork setup the engine does state maintenance for you. The
**weekly state-review** Todoist task fires every Sunday with a
checkbox per state mutation; the next cron picks up your checked
boxes and edits `state.yaml` on your behalf. Two persistent tasks —
**🛑 Emergency pause** and **▶️ Resume** — sit always-on in the
inbox for unplanned breaks. Result: in the steady-state flow, you
never open `state.yaml`.

- **Advance a module.** On Sunday, check the "I'm ready to advance
  to Module N+1" sub-task on the weekly state-review parent. Next
  cron bumps `current_module`, the new module's onboarding task
  fires the following morning. `revert_last` (also on the Sunday
  review) undoes it if you checked the box by accident.
- **Mark a book finished or started.** Check the corresponding
  sub-task on the Sunday review.
- **Increment a counter** (e.g. Anki cards added this week). Check
  the sub-task, drop the integer count into a Todoist comment on
  that sub-task; engine reads the first comment and adds it.
- **Pause unexpectedly.** Check the persistent **🛑 Emergency pause**
  task. Next cron sets `paused: true` and stops creating study tasks.
  When you're back, check **▶️ Resume**.
- **Planned pause** (vacation, etc.). Author a `set_pause` action
  with explicit `days` on a one-off sub-task — engine auto-unpauses
  when the timer elapses (no need to manually resume).
- **Month + phase.** Engine-managed. `month` and `phase` derive from
  calendar elapsed days minus closed pause intervals; you no longer
  edit them.
- **Add a new ritual.** Append a template to the appropriate
  `curriculum/rituals/*.yaml`. The id must be unique across the
  whole curriculum.
- **Change phases / books mid-stream.** Edit `curriculum/syllabus.yaml`
  directly. The validator catches inconsistencies (titles, phase
  numbers, etc.) at startup.
- **Track a course or certification in parallel.** Declare it once
  in `curriculum/syllabus.yaml` under `tracks:` (title, category,
  phase, optional `months: [start, end]`). The validator then
  requires every entry in `state.learning_tracks` to match a
  declaration — typos fail fast. Lifecycle states are
  `not_started | current | done`. With `months:` the engine
  auto-transitions at month boundaries (owner state always wins on
  conflict); without `months:` the owner advances state manually
  via the weekly state-review (the review parent auto-injects one
  finish-checkbox per `current` track). Gate any ritual template
  on track state via `gated_by:` — e.g., a weekly boot.dev
  session that only fires while the track is `current`. See
  [`AGENTS.md`](../AGENTS.md) Step 5.75 for the full schema.
- **Audit / undo deeper than one step.** `state_log.yaml` records
  every mutation (timestamp, action, prior/new). Use `git revert` of
  the cron commit to roll back further.

**Escape hatch.** If you do want sub-day-latency state changes,
edit `state.yaml` directly and commit. The next cron picks up the
edit immediately. Useful when correcting a runaway counter or
unwinding a botched series of mutations.

## When things break

- **`CurriculumError` on startup** — read the message; fix the
  named file.
- **Task that shouldn't appear keeps appearing** — check
  `.task_cache.json` for its `external_id`. The cache key includes
  the template id + a date component, so the same template fires
  fresh each day; dedup only prevents the same template from firing
  twice within its cadence window.
- **Dashboard looks stale** — the cron must run for the dashboard to
  regenerate. Trigger a workflow_dispatch from the Actions tab.
- **Tests failing in CI but not locally** — open an issue with the
  failing test name and the GitHub Actions log URL.

## Going deeper

- [`AGENTS.md`](../AGENTS.md) — full schema reference + AI-driven
  curriculum design protocol.
- [`SPEC.md`](../SPEC.md) — the engine's original design doc
  (historical, written for the 39-month "long way" curriculum, but
  the architecture description still applies).
- [`docs/superpowers/specs/2026-05-22-pluggable-curriculum-design.md`](./superpowers/specs/2026-05-22-pluggable-curriculum-design.md)
  — the design doc for the pluggable-curriculum refactor that made
  this fork-friendly.
