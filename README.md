# long-way-engine

A pluggable engine for running multi-month learning plans. You describe
your plan in YAML (phases, books per month, modules, daily/weekly/monthly
rituals); the engine creates the right Todoist tasks every morning,
generates reflection markdown stubs on cadence, and renders a static
dashboard of your progress.

## Designing your own plan

The hard part of forking this isn't the engine — it's writing the
curriculum. To make that tractable, the repo ships
**[`AGENTS.md`](./AGENTS.md)**: a self-contained brief that any
capable AI agent (Claude, Cursor, Codex, etc.) can read to
interview you and produce a complete `curriculum/` bundle for your
fork.

The intended workflow:

1. Fork this repo.
2. Open it in your AI tool of choice. Tell the agent:
   > "Read AGENTS.md and run the 7-step interview to build my curriculum."
3. Answer questions for ~30 minutes — goal, duration, phases, books
   per month, modules, rituals. The agent writes every YAML file in
   `curriculum/` as you go.
4. Run `python -m src.main --dry-run` to verify the agent's output.
5. Wire up Todoist + GitHub Actions per [`docs/FORKING.md`](./docs/FORKING.md).

`AGENTS.md` is the spec for how the fork should be written. It
contains the full schema for every file, the validation rules the
engine enforces, the interview protocol, and anti-patterns to
avoid. Treat it as the canonical contract — your fork is well-formed
if and only if its `curriculum/` satisfies what `AGENTS.md` describes.

If you'd rather skip the interview and start from a working example,
copy one of the starter bundles in [`examples/`](./examples/) into
`curriculum/` and edit it. Full setup instructions:
[`docs/FORKING.md`](./docs/FORKING.md).

## How this started

This was originally a single-user system for one specific 39-month
syllabus — Saurav's [`the-long-way.md`](./the-long-way.md), a personal
plan to become a serious software engineer the slow, deliberate way:
mornings on paper books, evenings in a terminal, weekly retrievals,
monthly public writeups. The whole syllabus, every ritual, every
phase boundary was baked into Python code.

Around month one, it became clear that the engine itself — the
"task-template-with-cadences + dashboard + reflection log" machinery —
was generic. The curriculum was the only opinionated part. So the
curriculum got lifted out into `curriculum/*.yaml`, and `AGENTS.md`
was added so an AI agent can interview anyone and produce a complete
bundle. Fork the repo, write your own `curriculum/`, point the daily
cron at it, and you have a personal learning system.

The original 39-month plan still lives in this repo as
[`curriculum/syllabus.yaml`](./curriculum/syllabus.yaml). Two
hand-built example curricula in [`examples/`](./examples/) (a 12-month
ML engineer path and a 6-month frontend deep-dive) show what other
shapes look like.

## What it does

- **Daily Todoist tasks.** Templates declare cadence (`daily`,
  `weekly`, `monthly`, `quarterly`, `annual`, `once-per-module`) +
  optional skip rules (`sunday`, `pair_day`, `last-saturday-of-month`).
  Engine resolves placeholder variables (`{current_book}`,
  `{ritual_times.morning_reading}`, `{iso_year}-W{iso_week:02d}`) and
  creates one task per template that fires today. Deduped via local
  cache.
- **Reflection markdown stubs.** Weekly / monthly / quarterly /
  annual ritual templates auto-create empty markdown files at the
  right path; you fill them in throughout the period.
- **Static dashboard.** Every successful daily run regenerates
  `docs/index.html`: current phase, month, module, streaks, books
  read, completion percentages, reflection log links.
- **Failure-isolated.** Validator runs at startup; if anything in
  your curriculum is malformed, you see every problem at once and
  no Todoist tasks get created until you fix them.

## Local setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env, set TODOIST_TOKEN
# edit config.yaml, set todoist.project_id
```

Run a one-off:

```bash
python -m src.main
```

Run tests:

```bash
pytest
```

## Production

`.github/workflows/daily.yml` runs at 03:00 Asia/Kolkata (21:30 UTC) and on `workflow_dispatch`. The repo secret `TODOIST_TOKEN` must be set.

## Pause / unpause ritual (Phase E)

Pause and unpause are owner edits to `state.yaml`. The dashboard reads
both the open and the closed pause windows so streak walks are not
broken by genuine off-time.

**Pausing.** When you decide to pause:

```yaml
paused: true
paused_since: 2026-08-15   # the day you stopped
```

**Unpausing.** When you come back, append a closed interval to
`pause_history`, clear `paused_since`, and flip `paused` back to false:

```yaml
paused: false
paused_since: null
pause_history:
  - start: 2026-08-15      # what was previously in paused_since
    end:   2026-09-02      # today (the day you resumed)
    reason: "two-week travel"
```

`pause_history` is append-only; never edit a closed interval after the
fact. The dashboard considers any date inside a closed interval — and
any date on or after `paused_since` while `paused: true` — as a "skip
day": neither counted toward streaks nor a break in them.

## `books_state` (Phase E)

`state.yaml` carries an owner-maintained map from book title to one of
three values:

```yaml
books_state:
  Computer Systems\: A Programmer's Perspective: current
  Computer Networking\: A Top-Down Approach: not_started
  Debugging\: The 9 Indispensable Rules: done
```

Valid values: `not_started`, `current`, `done`. The dashboard's Books
section renders a per-phase list from `curriculum/syllabus.yaml`'s
`books:` entries and tags each with the badge from this map. Titles
must match exactly; absence defaults to `not_started`.

## Dashboard (Phase E)

Every successful daily run regenerates `docs/index.html` and
`docs/assets/data.json`. CSS at `docs/assets/style.css` is committed
once and left alone afterwards — hand-edit for visual tweaks.

To opt out of dashboard render on a single run: `--skip-dashboard`.
Dry-run never renders.

### GitHub Pages enablement (one-time)

Settings → Pages → Source: **Deploy from a branch** → Branch: `main` /
folder: `/docs` → Save. The dashboard then publishes at:

```
https://<github_username>.github.io/<repo_name>/
```

`config.yaml`'s `dashboard.github_username` + `dashboard.repo_name`
must already match your GitHub URL — the reflection-log links use them
to build per-file blob URLs.

## Fork it for your own plan

See [`docs/FORKING.md`](./docs/FORKING.md) for the full 10-step
setup guide.

The recommended way to come up with your curriculum is the
AI-agent interview described in [`AGENTS.md`](./AGENTS.md) — see
[Designing your own plan](#designing-your-own-plan) above.

Starter bundles, if you want to skip the interview and edit a
working example:

- [`examples/ml-engineer-12mo/`](./examples/ml-engineer-12mo/) — 12-month ML engineer path (3 phases, 9 modules)
- [`examples/frontend-craft-6mo/`](./examples/frontend-craft-6mo/) — 6-month frontend deep-dive (2 phases, 6 modules)
