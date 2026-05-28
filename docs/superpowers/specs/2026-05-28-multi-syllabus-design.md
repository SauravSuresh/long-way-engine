# Multi-syllabus support — design

**Status:** draft
**Date:** 2026-05-28
**Author:** PrevizKompany (with Claude)

## Problem

The engine currently runs exactly one syllabus per repo. `config.yaml`
points at a single `curriculum_dir`; `state.yaml` carries a flat
`current_module` / `current_book` / `completed_modules` / `books_state`;
the daily cron walks one template tree and fires into one Todoist
project; the dashboard renders one phase/month/module view.

The owner wants to run a second syllabus — a shorter, job-readiness
plan — in parallel with the existing 39-month "Long Way" path. That is
not expressible today: there is one set of state pointers, one Todoist
target, one dashboard surface, one weekly state-review task.

`state.yaml`'s `learning_tracks` already models *parallel surfaces*,
but only as status badges (`current` / `done` / `not_started`). A
learning track does not fire its own daily tasks, advance through its
own modules, render its own dashboard card, or own a Todoist project.
A second syllabus needs all of those.

## Goal

1. Run N syllabuses concurrently from one repo, one daily cron, one
   GitHub Pages site.
2. Each syllabus is a fully self-contained content bundle: phases,
   books, modules, ritual templates, reflection templates.
3. Per-syllabus state, streak, pause, Todoist project, weekly
   state-review task, reflection subfolder, current_module /
   current_book pointers.
4. Owner controls priority and clock times per syllabus through a
   single top-level edit to `config.yaml`. Syllabuses themselves
   declare *what work* (which slots they need, at which cadences) but
   never *when* (no clock times inside `curricula/<name>/`).
5. Existing single-syllabus forks migrate cleanly via a one-shot
   script. No surprise breakage for users who copied an `examples/`
   bundle.

## Non-goals

- Cross-syllabus dependency graphs (no "finish module 3 of A before
  module 1 of B").
- Global pause. Pause is per-syllabus; pausing one does not pause
  another.
- Cross-syllabus shared streaks. Each syllabus has its own streak,
  computed from its own completion + pause history.
- Auto-resolving slot conflicts. The validator errors when two enabled
  syllabuses resolve to the same `(ritual_times_key, clock_time)`
  pair. The owner must override one or set `allow_slot_overlap: true`
  on a syllabus block.
- Dynamic add/remove of syllabuses via Todoist checkbox. Adding a
  syllabus is a `config.yaml` edit + new `curricula/<name>/` bundle.
- Multi-tenant. Still one owner, one Todoist account, one GitHub Pages
  site.

## Shape of the change

### Repo layout

```
long-way-engine/
├── config.yaml                      # top-level: priority_order, syllabuses{}, dashboard
├── state/
│   ├── shared.yaml                  # timezone, anki_card_count, prs_opened, notes
│   ├── long-way.yaml                # per-syllabus state slice
│   └── job-readiness.yaml
├── curricula/
│   ├── long-way/                    # renamed from curriculum/
│   │   ├── syllabus.yaml
│   │   ├── manifest.yaml
│   │   ├── modules.yaml
│   │   ├── rituals/
│   │   └── reflection_templates/
│   └── job-readiness/
│       └── ...
├── reflections/
│   ├── long-way/                    # auto-created stubs land here
│   └── job-readiness/
├── docs/                            # one HTML page, per-syllabus cards
└── src/
```

`the-long-way.md` stays at the repo root; it's owner narrative, not
engine input.

### `config.yaml` new shape

```yaml
# Shared time defaults. Each syllabus inherits these unless it overrides
# them in its own ritual_times block below.
ritual_times:
  morning_reading: "06:00"
  anki: "08:30"
  evening_hands_on: "19:00"
  friday_review: "20:00"
  saturday_deep_block: "09:00"
  sunday_trace: "19:00"
  weekly_state_review: "10:00"

# Order matters: foreground first. Drives dashboard card order, Todoist
# task creation order (primary appears at top of its project), and
# tie-breaking when slots collide.
priority_order:
  - job-readiness
  - long-way

# Per-syllabus block. Adding a syllabus = add an entry here and a
# curricula/<key>/ bundle.
syllabuses:
  long-way:
    path: curricula/long-way
    todoist_project_id: "6gWxC2wh5WRvjfw2"
    state_file: state/long-way.yaml
    enabled: true
    ritual_times:                    # optional override of top-level
      morning_reading: "06:00"
      evening_hands_on: "19:00"
    allow_slot_overlap: false        # default; explicit for clarity

  job-readiness:
    path: curricula/job-readiness
    todoist_project_id: "<TBD-by-user>"
    state_file: state/job-readiness.yaml
    enabled: true
    ritual_times:
      morning_reading: "13:00"
      evening_hands_on: "21:00"

# Shared cadence config — applies to every syllabus.
sunday_off: true
pair_day: thursday

dashboard:
  github_username: "SauravSuresh"
  repo_name: "long-way-engine"
```

The effective `ritual_times` for a syllabus = top-level merged with the
per-syllabus override. Missing keys inherit; present keys override.

### State files

`state/shared.yaml` — user-life-wide; one set across all syllabuses.

```yaml
timezone: Asia/Kolkata
anki_card_count: 0
manual_counters:
  prs_opened: 0
  traces_completed: 0
  lineage_detours_done: []
notes: |
  ...
```

`state/<syllabus>.yaml` — one per syllabus.

```yaml
start_date: 2026-05-05
phase: 1
month: 1
current_module: 1
current_book: "Computer Systems: A Programmer's Perspective"
completed_modules: []
books_state:
  Computer Systems\: A Programmer's Perspective: current
learning_tracks:
  Courses:
    "boot.dev backend path": current
paused: false
paused_since: null
pause_history: []
```

Streak is computed at render time from this file's completion history
and pause windows; not stored.

## Engine internals

`src/main.py` becomes a foreach over enabled syllabuses in
`priority_order`. For each: load its state slice + shared state, walk
its templates, resolve placeholders against its slice + shared, fire to
its Todoist project, dedup against its cache namespace, render its
dashboard card.

| Module | Change |
|---|---|
| `config.py` | Load `syllabuses:` map. Resolve effective `ritual_times` per syllabus = top-level merged with per-syllabus override. Validate `priority_order ⊆ syllabuses.keys()` and `set(priority_order) == set(enabled syllabuses)`. Reject duplicate `(slot, clock_time)` across enabled syllabuses unless that syllabus has `allow_slot_overlap: true`. |
| `state.py` | Split into `SharedState` (loads `state/shared.yaml`) and `SyllabusState` (loads `state/<name>.yaml`). Existing single-state callers refactored to take an explicit `SyllabusState` argument. |
| `syllabus.py` | Constructor takes a syllabus path; same parser otherwise. One instance per syllabus. |
| `scheduler.py` | Operates on one syllabus at a time. Walks its ritual templates + module templates. Placeholders resolve against that syllabus's state + shared. Skip rules (`sunday`, `pair_day`) unchanged. Each emitted task carries a `syllabus_key`. |
| `templates.py` | No conceptual change. `{current_book}` now resolves from the active syllabus's state, not a global. |
| `todoist.py` | `create()` routes by `syllabus_key → project_id` from config. Adds Todoist label `syllabus:<key>` on every created task. |
| `cache.py` | Cache key prefixed with `syllabus_key`. Layout: `{ "<syllabus>": { "<template_id>:<date>": "<todoist_id>" } }`. Migration shim: on first multi-syllabus run, flat `.task_cache.json` keys move under `long-way`. |
| `state_review.py` | One weekly state-review template per syllabus (sourced from that syllabus's `rituals/weekly.yaml`). Each fires into its own Todoist project. |
| `state_mutations.py` | Each state-review task carries a `syllabus:<key>` label; the mutation parser reads it and writes to `state/<key>.yaml`. Shared mutations (anki counter, prs_opened) go to `state/shared.yaml`. |
| `reflections.py` | Stub path becomes `reflections/<syllabus_key>/<cadence>/<period>.md`. Reflection templates live per-syllabus at `curricula/<key>/reflection_templates/`. |
| `streaks.py` | Compute per syllabus from that syllabus's completion + pause history. No cross-syllabus stitching. |
| `dashboard.py` | Top-level page restructure. Shared header band (timezone, Anki count, prs_opened, etc.). Below: one card per enabled syllabus in `priority_order` — phase/month/module, current book, books_state, learning_tracks, streak, pause status, recent reflections links. Paused syllabus card renders muted with `[paused since YYYY-MM-DD]` badge. Disabled syllabus omitted. |
| `curriculum_validator.py` | Per-syllabus validation unchanged. New cross-cutting checks: priority_order completeness, slot collisions, missing state files for declared syllabuses, missing reflection_templates dir, Todoist project_id format. |

### Placeholder scope

- Per-syllabus (resolve against active syllabus state): `{current_book}`, `{current_module}`, `{next_module}`, `{next_book}`, `{current_phase_name}`.
- Shared (clock-only, unchanged): `{iso_year}`, `{iso_week}`, `{year}`, `{month}`, `{quarter}`.
- New optional: `{syllabus_name}` — the syllabus key, for users who want to embed it in task content.

### Cache file location

`.task_cache.json` and `.completion_cache.json` stay at the repo root.
Internal structure is namespaced by syllabus. File path unchanged to
avoid `.gitignore` churn.

## Dashboard layout

Single `docs/index.html`. Approximate layout:

```
┌─────────────────────────────────────────────────────────┐
│  long-way-engine                                        │
│  Asia/Kolkata · Anki: 1,247 · PRs opened: 8             │
├─────────────────────────────────────────────────────────┤
│  ▸ Job Readiness               [priority 1] [active]    │
│    Phase 1 · Month 2 · Module 3                          │
│    Current book: Cracking the Coding Interview          │
│    Streak: 18 days                                       │
│    Books read: 1/4   Modules done: 2/6                   │
│    Reflections: 2026-W21 · 2026-04 · ...                │
├─────────────────────────────────────────────────────────┤
│  ▸ Long Way                    [priority 2] [active]    │
│    Phase 1 · Month 1 · Module 1                          │
│    Current book: Computer Systems: A Programmer's...    │
│    Streak: 24 days                                       │
│    Books read: 0/12  Modules done: 0/N                   │
│    Reflections: 2026-W21 · 2026-04 · ...                │
└─────────────────────────────────────────────────────────┘
```

`docs/assets/data.json` becomes:

```json
{
  "shared": { "timezone": "...", "anki_card_count": 1247, "manual_counters": {...} },
  "syllabuses": {
    "long-way": { "phase": 1, "month": 1, "current_module": 1, "streak": 24, ... },
    "job-readiness": { ... }
  },
  "priority_order": ["job-readiness", "long-way"]
}
```

## Reflection paths

```
reflections/
├── long-way/
│   ├── weekly/2026-W21.md
│   ├── monthly/2026-04.md
│   ├── quarterly/2026-Q2.md
│   └── annual/2026.md
└── job-readiness/
    └── weekly/2026-W21.md
```

## Migration

`scripts/migrate_to_multi_syllabus.py`:

1. `git mv curriculum/ curricula/long-way/` (preserves history).
2. Split `state.yaml`:
   - `timezone`, `manual_counters`, `notes`, `anki_card_count` → `state/shared.yaml`.
   - `start_date`, `phase`, `month`, `current_module`, `current_book`, `completed_modules`, `books_state`, `learning_tracks`, `paused`, `paused_since`, `pause_history` → `state/long-way.yaml`.
3. Rewrite `config.yaml` to new shape. Single entry under `syllabuses:` keyed `long-way`. Copy existing `project_id` and `ritual_times` over.
4. Move existing `reflections/<file>` → `reflections/long-way/<cadence>/<file>`.
5. Wrap `.task_cache.json` and `.completion_cache.json` contents under a `"long-way"` top-level key.
6. Run validator in dry-run mode. Abort with rollback if anything fails.

Single existing fork = run script once and continue without behavior
change. Then the owner adds `curricula/job-readiness/` + the
`state/job-readiness.yaml` + `syllabuses.job-readiness` block to start
the second path.

## Testing

- `tests/golden/YYYY-MM-DD.json` fixtures gain a `syllabus_key` field per task. Existing fixtures retro-fitted with `syllabus_key: long-way`.
- New golden fixtures with two syllabuses enabled lock in slot-collision behavior, priority order, and per-syllabus state mutations.
- New unit tests:
  - `config.py`: override merging, priority_order validation, slot collision detection, `allow_slot_overlap` escape hatch.
  - `state.py`: shared vs per-syllabus split, missing-file errors.
  - `cache.py`: namespacing, migration shim idempotency.
  - `dashboard.py`: renderer with 1, 2, N syllabuses; paused state; disabled syllabus.
  - `scripts/migrate_to_multi_syllabus.py`: idempotency, rollback on validation failure.
- All existing tests must pass against the migrated single-syllabus shape (semantics-preserving migration).

## Forker impact

- `AGENTS.md` updated: interview asks "single syllabus or multiple?" up front; default = single. Output layout is `curricula/<name>/` even for single-syllabus forks so there is no second migration later.
- `docs/FORKING.md` updated for new paths.
- `examples/*` bundles relocated under `curricula/<name>/` in docs for shape consistency.
- README rewritten around the new structure with a "Adding another syllabus" section.

## Open questions

None as of approval. Slot-collision UX (a single hard error vs. a
warning + suppression list) may need a follow-up if it turns out to be
chatty in practice.

## Related specs

- [`2026-05-22-pluggable-curriculum-design.md`](./2026-05-22-pluggable-curriculum-design.md) — the original single-syllabus pluggability work this builds on.
- [`2026-05-23-curriculum-tracks-design.md`](./2026-05-23-curriculum-tracks-design.md) — `learning_tracks` design; tracks remain per-syllabus.
- [`2026-05-23-state-review-todoist-design.md`](./2026-05-23-state-review-todoist-design.md) — weekly state-review pattern; now fires once per syllabus.
