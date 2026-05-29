# long-way-engine

This is the engine I built to run a 39-month plan to become a serious
software engineer the slow, deliberate way: mornings on paper books,
evenings in a terminal, weekly retrievals, monthly public writeups,
quarterly synthesis essays. The full syllabus lives in
[`the-long-way.md`](./the-long-way.md); the curriculum data the
engine reads lives in [`curricula/long-way/`](./curricula/long-way/).

Every morning a GitHub Action creates today's Todoist tasks for me —
the right ones for whichever month, module, and weekday I'm on, with
the right book name interpolated into the morning-reading task.
Reflection markdown stubs auto-generate on cadence. A static
dashboard at the repo's GitHub Pages site shows my current phase,
streaks, books read, and the full reflection log.

## Multiple syllabuses

The engine runs N syllabuses in parallel from one repo, one daily cron, one
GitHub Pages site. Each syllabus is a self-contained content bundle at
`curricula/<key>/` with its own modules, books, rituals, and reflection
templates; each gets its own Todoist project, streak, pause state, and
dashboard card.

`config.yaml` declares the ordering and per-syllabus overrides:

    priority_order:
      - long-way
    syllabuses:
      long-way:
        path: curricula/long-way
        todoist_project_id: "<your project id>"
        state_file: state/long-way.yaml
        enabled: true
        ritual_times:
          morning_reading: "06:00"   # overrides top-level if set

`priority_order` controls dashboard card order and Todoist task creation
order. Shared rhythm comes from the top-level `ritual_times`; each syllabus
inherits unless its `ritual_times` block overrides a slot. Two syllabuses
declaring the same `(slot, clock_time)` pair without `allow_slot_overlap`
on at least one side fails fast at startup.

Per-syllabus state lives at `state/<key>.yaml`; user-life-wide state
(timezone, Anki count, manual counters, notes) lives at `state/shared.yaml`.
Pause and streak are per-syllabus.

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
  right path; I fill them in throughout the period.
- **Static dashboard.** Every successful daily run regenerates
  `docs/index.html`: current phase, month, module, streaks, books
  read, completion percentages, reflection log links.
- **Failure-isolated.** Validator runs at startup; if anything in
  the curriculum data is malformed, every problem surfaces at once
  and no Todoist tasks get created until it's fixed.

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

`.github/workflows/daily.yml` runs at 03:00 Asia/Kolkata (21:30 UTC)
and on `workflow_dispatch`. The repo secret `TODOIST_TOKEN` must be
set.

## Local tooling

Two scripts run locally and never call Todoist.

- **`scripts/show_timetable.py`** — Preview the resolved weekly schedule
  before pushing a `config.yaml` change. Surfaces `(slot, time)` collisions
  across enabled syllabuses with a visible marker. Exit code is non-zero
  if any collision exists, so it can be wired into a pre-commit hook.

      python -m scripts.show_timetable
      python -m scripts.show_timetable --syllabus long-way
      python -m scripts.show_timetable --json

- **`scripts/migrate_to_multi_syllabus.py`** — One-shot migration for an
  existing single-syllabus fork. Moves `curriculum/` → `curricula/<name>/`,
  splits `state.yaml` into `state/shared.yaml` + `state/<name>.yaml`,
  rewrites `config.yaml` to the new shape, wraps caches and reflections
  under the syllabus key. Idempotent.

      python -m scripts.migrate_to_multi_syllabus --dry-run
      python -m scripts.migrate_to_multi_syllabus --name long-way

## Pause / unpause ritual

Pause and unpause are per-syllabus. Edit the appropriate
`state/<key>.yaml` (e.g. `state/long-way.yaml`). The dashboard reads
both the open and the closed pause windows so streak walks are not
broken by genuine off-time.

**Pausing.** When I decide to pause:

```yaml
paused: true
paused_since: 2026-08-15   # the day I stopped
```

**Unpausing.** When I come back, append a closed interval to
`pause_history`, clear `paused_since`, and flip `paused` back to false:

```yaml
paused: false
paused_since: null
pause_history:
  - start: 2026-08-15      # what was previously in paused_since
    end:   2026-09-02      # today (the day I resumed)
    reason: "two-week travel"
```

`pause_history` is append-only; never edit a closed interval after the
fact. The dashboard considers any date inside a closed interval — and
any date on or after `paused_since` while `paused: true` — as a "skip
day": neither counted toward streaks nor a break in them.

## Modules vs `learning_tracks` — the spine and the parallel surfaces

The curriculum has two orthogonal kinds of work, and the engine
models them differently on purpose.

**Modules are the linear spine.** `current_module` is a single
integer pointer that only advances. Each module defines the work of
a time block (~2–6 weeks). The validator enforces dense `1..N`
numbering and one phase per module. Module names carry whatever
the work is about — a course, a project, a deep dive into a book.

```yaml
# curricula/<name>/syllabus.yaml
modules:
  - number: 7
    name: "Neuromatch Academy (or self-paced compneuro)"
    phase: 2
    estimated_hours: 90
```

**Learning tracks are the parallel always-on surfaces.** Courses
you're auditing across months, certifications you're chasing
across years, branches off the trunk, lineage detours. They live
in `state/<key>.yaml` under arbitrary owner-defined categories:

```yaml
# state/<key>.yaml
learning_tracks:
  Courses:
    "boot.dev backend path": current
  Certifications:
    "LFCS": current
  Active branches:
    "Text editor in C": current
  Lineage detours:
    "Module 6 detour: bytecode VM": not_started
```

Categories and item names are arbitrary strings — the engine never
validates them. A typo in `Lineage detours` produces a silent extra
category at first render rather than an error (this is
intentional; the field is uniformly owner-agency).

**Rule of thumb:** if the thing IS the work of a defined time
block, it's a module. If it runs in parallel with the spine, it's
a `learning_tracks` entry. Books have their own surface
(`books_state`) — see below.

Tracks the curriculum acknowledges are declared in
`syllabus.yaml` under `tracks:`; the validator rejects entries in
`state.learning_tracks` that don't match a declaration, so typos
fail fast. Ritual templates can gate on track state via
`gated_by:` — e.g., a `weekly-bootdev-session` template that only
fires while the boot.dev track is `current`. Declarations with
`months: [start, end]` opt into automatic `not_started -> current
-> done` transitions at month boundaries; absence keeps the
lifecycle manual. See [`AGENTS.md`](./AGENTS.md) Step 5.75 for
the full vocabulary.

## `books_state`

`state/<key>.yaml` carries an owner-maintained map from book title to one of
three values:

```yaml
books_state:
  Computer Systems\: A Programmer's Perspective: current
  Computer Networking\: A Top-Down Approach: not_started
  Debugging\: The 9 Indispensable Rules: done
```

Valid values: `not_started`, `current`, `done`. The dashboard's Books
section renders a per-phase list from `curricula/<name>/syllabus.yaml`'s
`books:` entries and tags each with the badge from this map. Titles
must match exactly; absence defaults to `not_started`.

## Dashboard

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

---

## Fork it — have this for yourself

I built this for me, but the engine itself is generic. The curriculum
data is the only opinionated part, and it lives in YAML you can
replace wholesale. Fork the repo, write your own `curricula/<name>/`,
point the daily cron at it, and you have your own personal learning system
firing tasks at you every morning.

The hard part of forking isn't the engine — it's writing the
curriculum. To make that tractable, the repo ships
**[`AGENTS.md`](./AGENTS.md)**: a self-contained brief that any
capable AI agent (Claude Code, Cursor, Codex, Aider) can read to
interview you and produce a complete `curricula/<name>/` bundle for
your fork.

### The workflow

1. Fork this repo.
2. Open it in your AI tool of choice. Send the agent something like:

   > Read `AGENTS.md` end to end. Then run the 7-step interview
   > with me to build my curriculum. **I want to be a person who
   > can build a Raspberry-Pi-based home server from bare metal —
   > pick the chip, solder the board, flash a kernel I compiled
   > myself, and host my own services on it.** Aim for 9 months.

3. Answer the agent's questions for ~30 minutes — goal, duration,
   phases, books per month, modules, rituals. The agent writes every
   YAML file in `curricula/<name>/` as you go.
4. Run `python -m src.main --dry-run` to verify the agent's output.
5. Wire up Todoist + GitHub Actions per [`docs/FORKING.md`](./docs/FORKING.md).

### What to actually say to the agent

Pin a concrete capability and a horizon. The interview goes better
when the goal is identity-shaped ("a person who can X") than when
it's topical ("learn X"). Some examples that work:

> I want to be a person who can **build my own mechanical keyboard
> from scratch — schematic, PCB, firmware, the lot.** 6 months.

> I want to **read classical Arabic poetry in the original by
> month 12, and recite one ode from memory.**

> I want to **ship a small multiplayer game to Steam — net code I
> wrote myself, art that doesn't embarrass me, paying customers.**
> 18 months.

> I want to **deploy a 3-node Kubernetes cluster on bare-metal
> hardware in my apartment** and run my own services on it.
> 9 months.

> I want to **read modern ML papers fluently and re-implement one
> paper a month for a year**, ending with a publishable result.

> I want to go from **never having touched a piano to performing a
> Chopin nocturne live** at an open mic. 12 months.

> I want to **bake bread good enough to sell at a Saturday market**,
> then actually do it. 8 months.

The agent reads `AGENTS.md`, asks clarifying questions, proposes a
phase split, lets you push back, then writes a full `curricula/<name>/`
bundle that matches what the engine knows how to run.

### Why `AGENTS.md` is the contract

`AGENTS.md` is the spec for how a well-formed fork should be written.
It contains the full schema for every file, the validation rules the
engine enforces at startup, the interview protocol, and anti-patterns
to avoid — including a default the agent will insist on:
**a daily spaced-repetition ritual, regardless of your domain.**
Long-horizon learning without SRS loses ~80% of what you covered
inside a month, which is why every curriculum the agent generates
includes it.

If you'd rather skip the interview and start from a working example,
copy one of the starter bundles in [`examples/`](./examples/) into
`curricula/<name>/` and edit it:

- [`examples/ml-engineer-12mo/`](./examples/ml-engineer-12mo/) — 12-month ML engineer path (3 phases, 9 modules)
- [`examples/frontend-craft-6mo/`](./examples/frontend-craft-6mo/) — 6-month frontend deep-dive (2 phases, 6 modules)
- [`examples/programmer-to-neuroscience-12mo/`](./examples/programmer-to-neuroscience-12mo/) — 12-month programmer-to-neuroscientist path (3 phases, 12 modules)

Each example includes a **weekly state-review** task whose sub-task
checkboxes mutate `state/<key>.yaml` on the next cron — module advance,
book transitions, pause, Anki counter, revert. After fork setup
you never hand-edit `state/<key>.yaml`.

Full setup walkthrough: [`docs/FORKING.md`](./docs/FORKING.md).

## Adding another syllabus

To run a second path alongside your current one:

1. Copy or scaffold a new bundle at `curricula/<new-key>/` (use one of
   `examples/` or run the `AGENTS.md` interview to generate it).
2. Create `state/<new-key>.yaml` seeded with that syllabus's start date,
   current module, and current book.
3. Add a block under `syllabuses:` in `config.yaml`:

       syllabuses:
         long-way:
           ...
         <new-key>:
           path: curricula/<new-key>
           todoist_project_id: "<new project id>"
           state_file: state/<new-key>.yaml
           enabled: true

4. Add `<new-key>` to `priority_order` in the position you want.
5. Run `python -m scripts.show_timetable` to verify no slot collisions.
6. Commit.

The next cron run will fire tasks for both syllabuses into their own
Todoist projects and render both as cards on the dashboard.
