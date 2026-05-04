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
