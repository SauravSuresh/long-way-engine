# long-way-engine

Personal task-engine for a 3-year learning syllabus. GitHub Actions creates Todoist tasks daily; reflections live as version-controlled markdown; a static dashboard renders progress.

See `SPEC.md` for the full design and `the-long-way.md` for the syllabus the engine serves. `STATUS.md` tracks what's built versus what's planned.

## Phase A scope

This is the walking skeleton. Two daily Todoist tasks (morning reading, Anki) get created at 03:00 Asia/Kolkata, idempotently, with a content marker for future reconstruction. No weekly/monthly/quarterly cadences yet, no reflections, no dashboard.

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
section renders a per-phase list using `parse_books` against
`the-long-way.md` and tags each entry with the badge from this map.
Titles must match exactly; absence defaults to `not_started`.

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

## Fork it for your own curriculum

This repo runs my 39-month "long way" plan, but the engine is generic.
Forkers can replace `curriculum/` with their own bundle. See
[`AGENTS.md`](./AGENTS.md) for the full schema and a recommended
interview protocol you can run with an AI coding agent.

Two starter bundles in [`examples/`](./examples):

- `examples/ml-engineer-12mo/` — 12-month ML engineer path
- `examples/frontend-craft-6mo/` — 6-month frontend deep-dive

To use one: copy it to `curriculum/`, edit `config.yaml`'s
`curriculum_dir` if you put it elsewhere, then run
`python -m src.main --dry-run` to see what fires today.
