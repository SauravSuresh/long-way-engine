# Forking long-way-engine for your own learning plan

This guide walks you from a fresh fork to a daily-running engine that
creates Todoist tasks against your own curriculum and publishes a
progress dashboard.

If you'd rather have an AI agent build your curriculum for you,
read [`AGENTS.md`](../AGENTS.md) instead — that file is written for
AI agents and describes a 7-step interview they can run with you.

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

## Step 4 — Pick or build a curriculum

Two paths. Pick one.

### Path A — Start from an example bundle

```bash
rm -rf curriculum
cp -r examples/ml-engineer-12mo curriculum
# or:
cp -r examples/frontend-craft-6mo curriculum
```

Edit the copied files to your liking. The validator runs at startup
and will tell you if anything is malformed.

### Path B — Build your own from scratch

Read [`AGENTS.md`](../AGENTS.md). It contains:
- The full schema for every file in `curriculum/`.
- A 7-step interview protocol you can either run yourself or hand
  to an AI agent (Claude, Cursor, etc.) — just point the AI at
  `AGENTS.md` and say "help me build a curriculum".

Whichever path: by the end of this step you should have these
files in `curriculum/`:

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

# Optional parallel-learning categories (kanban-style buckets).
# Engine doesn't validate names — typos just produce extra
# categories in the dashboard.
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

- **Advancing modules.** When you finish a module, edit `state.yaml`:
  bump `current_module` to the next number. The engine's
  `module-N-onboarding` task for the new module will fire on the
  next run.
- **Advancing months.** Same idea: bump `month`. `current_book` is
  computed from `syllabus.primary_book_by_month` with carry-forward
  unless you've put an explicit override in `state.yaml`.
- **Pause / unpause.** Edit `state.yaml`'s `paused` and
  `pause_history` — see the section in the main [README](../README.md#pause--unpause).
- **Add a new ritual.** Append a template to the appropriate
  `curriculum/rituals/*.yaml`. The id must be unique across the
  whole curriculum.
- **Change phases / books mid-stream.** Edit `curriculum/syllabus.yaml`
  directly. The validator catches inconsistencies (titles, phase
  numbers, etc.) at startup.

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
