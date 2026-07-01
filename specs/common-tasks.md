# Feature spec — common (cross-curriculum) tasks

*Drafted 2026-07-01. Not implemented. Blocks the tracking-reset decision for
the devops-ready focus switch, so it is written up before touching streaks.*

---

## Goal

Let a task belong to the **owner**, not to a single syllabus. Some rituals
are life-wide, not curriculum-wide: spaced-repetition review is the first and
clearest case. Anki cards land in separate decks per topic, but reviewing all
decks is one cheap daily action — it should be **one task, once a day**, not
one Anki task per enabled curriculum that the owner mentally merges anyway.

Concretely, today both curricula author their own Anki ritual:

- `devops-ready/daily-devops-srs` → 07:30, devops Todoist project
- `long-way/weekly-saturday-anki` → 08:30 Sat, long-way Todoist project

That is two tasks for one habit, split across two projects, double-counted in
two streaks. The goal is a single **common bundle** whose tasks fire once,
into their **own Todoist project**, tracked by their **own streak**.

---

## Non-goals

- Not a general "shared library" of templates that curricula import. Common
  tasks are owned by the common bundle outright; curricula do not reference
  them.
- Not per-deck Anki tracking. One review action covers all decks. Card-count
  stays a single `anki_card_count` counter (already in `state/shared.yaml`).
- No change to the cadence / skip-rule / placeholder vocabulary. Common tasks
  use the same template schema as any ritual.
- Not retroactive. Existing cache entries for the old per-curriculum Anki
  tasks are left alone; they simply stop being recreated.

---

## Current behavior (what exists)

`src/main.py::main()` iterates `cfg.priority_order`; for each enabled
syllabus it calls `run_for_syllabus()`, which:

- creates Todoist tasks into `entry.todoist_project_id`,
- writes into a per-key cache slice `nc.data[key]`,
- derives a per-key streak spec set from templates flagged
  `counts_toward_streak: true` (`build_streak_specs`),
- returns a per-key dashboard card (`render_multi_syllabus`).

A bundle is a directory with `syllabus.yaml` + `manifest.yaml` +
`modules.yaml` + `rituals/*.yaml`, validated hard by
`src/curriculum_validator.py` (phases contiguous, modules dense, every module
has an onboarding task, etc.). There is **no** notion of a rituals-only
bundle today.

`state/shared.yaml` already holds the life-wide state (timezone,
`anki_card_count`, notes) — so a "common" concept partially exists at the
state layer but has no task-generation or dashboard surface.

---

## Design options

### Option A — first-class `common` bundle *(recommended)*

Add a top-level `common:` block in `config.yaml`, structurally like a
syllabus entry but pointing at a **rituals-only** bundle (no
`syllabus.yaml`, no modules/phases/books). The engine runs it in the daily
loop as a pseudo-syllabus with `syllabus=None`: it resolves only
date/`ritual_times` placeholders, creates tasks into its own project, keeps
its own cache slice and streak, and renders a compact dashboard card
(title + today's tasks + one streak). No fake curriculum scaffolding.

- **Pros:** correct model; clean dashboard; extensible (later: a common
  "daily walk", "journal", "inbox zero" ritual all live here).
- **Cons:** touches five engine files (see below). Needs a lighter validator
  path and a `syllabus=None`-tolerant run path.

### Option B — minimal syllabus at `curricula/common/` *(zero engine change)*

Dress the common bundle as a real syllabus: a 1-phase / 1-month / 1-module
`syllabus.yaml` with a dummy book ("Spaced Repetition"), one module
onboarding task, and the daily Anki ritual. Register it as a normal syllabus
with its own project.

- **Pros:** ships today, no code changes, reuses all machinery.
- **Cons:** the dashboard renders it as a full curriculum card — phase bar,
  module counter stuck at 1/1, a meaningless journey timeline. Semantically
  wrong even if functionally fine.

### Option C — engine-level dedup of identical task ids across syllabuses

Keep Anki authored in each curriculum but have the engine detect identical
`external_id`s across bundles and create the Todoist task only once.

- **Pros:** no new bundle concept.
- **Cons:** most invasive to the create/cache/dedup core; muddies per-syllabus
  cache ownership; still leaves the "which project?" and "which streak?"
  questions unanswered. Rejected.

**Recommendation: Option A.** It is the only option that models the domain
honestly. Option B is the acceptable fast path if the dashboard cruft is
tolerable for now; the migration below is written so A and B share the same
config shape and can swap later with no task churn.

---

## Detailed design (Option A)

### Config schema

```yaml
# config.yaml
common:
  path: curricula/common
  todoist_project_id: <NEW_PROJECT_ID>   # a dedicated "Common" Todoist project
  state_file: state/common.yaml
  enabled: true
  ritual_times:                          # same override/merge rules as syllabuses
    anki: '07:30'
```

`common` participates in the existing slot-collision check exactly like a
syllabus (so `anki@07:30` can't clash with anything else). It is **not** part
of `priority_order` (that stays the enabled-syllabus set); it always runs
first in the loop so its tasks/streak render at the top of the dashboard.

### Bundle layout

```
curricula/common/
├── manifest.yaml            # ritual_times_required: [anki]; no modules
└── rituals/
    └── daily.yaml           # the Anki template (below)
```

No `syllabus.yaml`, no `modules.yaml`.

```yaml
# curricula/common/rituals/daily.yaml
- id: common-srs-review
  title: "Anki — review all decks"
  description: |
    10–15 min. Every deck, every day — spaced repetition is cheap. Add
    3–5 new cards from whatever you studied today (any track). No more.
  due: "today at {ritual_times.anki}"
  labels: [daily-ritual, srs, common]
  cadence: daily
  skip_if: sunday
  counts_toward_streak: true
```

### State

`state/common.yaml` is a minimal `SyllabusState`: `start_date`, `paused`,
`pause_history` — enough for the streak/adherence walkers, which only read
those fields. No `current_module` / `month` / `books_state`. The loader must
tolerate their absence (default module=1/month=1, never surfaced).

### Engine changes (files touched)

1. **`src/config.py`** — parse the `common:` block into a `CommonEntry`
   (reuse `SyllabusEntry` shape; `path/project_id/state_file/enabled/
   ritual_times`). Include it in the collision scan.
2. **`src/syllabus.py`** — `load_syllabus` already tolerates a missing
   `syllabus.yaml`? No — it reads the file directly. Add `load_common_bundle`
   (or make the read optional) returning `syllabus=None` + parsed rituals.
3. **`src/main.py`** — before the `priority_order` loop, if `cfg.common` is
   enabled, run it through a `run_for_syllabus`-style path with
   `syllabus=None`: skip module-onboarding, book resolution, and
   state-review phases; keep task creation + sweep + streak specs.
   `resolve_variables` must already no-op on curriculum placeholders when
   `syllabus is None` (verify; `daily-evening-hands-on` legacy `run()` passes
   `syllabus=None`, so the path likely exists).
4. **`src/curriculum_validator.py`** — a `validate_common(bundle)` that runs
   only the ritual-level checks (rule 8 cadence, 9 skip_if, 10 unique ids, 13
   sub-task vocab, 6 ritual_times exist) and skips the phase/module/book/track
   rules (1–5, 7, 14–17).
5. **`src/dashboard.py`** — render the common bundle as a compact card: title,
   "today" task list, and its single streak/adherence. Reuse `_streaks_section`
   machinery; suppress phase bar / journey timeline / module counter when
   `syllabus is None`.

### Streak model (the part that unblocks the reset question)

- The common Anki owns a **global SRS streak** ("consecutive days you cleared
  your decks"). This is the single highest-signal habit and deserves its own
  number.
- **Remove Anki from the per-curriculum streaks.** After migration:
  - devops streak = morning study (Mon–Fri). *(boot.dev/LeetCode stay
    excluded — track-gated, would false-break.)*
  - long-way streak = Saturday CS:APP reading.
  Each curriculum streak then reads as "did I study this track," and SRS is
  graded once, globally — no more double-counting.
- `anki_card_count` counter is unchanged (already in `shared.yaml`); the
  common weekly/state surface can keep incrementing it, or the per-curriculum
  state reviews keep their existing counter sub-tasks.

---

## Migration steps

1. Create the "Common" project in Todoist; capture its project id.
2. Add the `common:` block to `config.yaml` (schema above).
3. Create `curricula/common/` (manifest + rituals/daily.yaml) and
   `state/common.yaml` (seed `start_date`).
4. **Remove Anki from the curricula:**
   - delete `devops-ready/daily-devops-srs`
   - delete `long-way/weekly-saturday-anki`
   - drop `counts_toward_streak` from those (they're gone) — devops streak
     falls back to morning study, long-way to Saturday reading.
   - `evening_hands_on` / `anki` slot cleanup in the affected manifests.
5. Implement engine changes 1–5 (Option A) **or**, for the fast path, do
   Option B and skip the code changes.
6. `python -m src.curriculum_validator curricula/common` (+ existing two).
7. `python -m scripts.show_timetable` → confirm one Anki row, no collisions.
8. `python -m src.main --dry-run --today <Mon>` and `<Sat>` → confirm exactly
   one Anki task fires per active day, in the Common project.

---

## Validation & testing

- Unit: `build_streak_specs` on the common bundle yields one daily spec;
  `daily_streak` counts consecutive non-Sunday days.
- Unit: config loader parses `common:` and includes it in collision detection.
- Dry-run: Sunday fires no Anki (skip_if sunday); Mon–Sat fire exactly one.
- Regression: devops/long-way dashboards no longer list Anki; their streaks
  grade against the remaining flagged templates only.

---

## Open questions

1. **Does Anki skip Sunday?** Current devops Anki does (`skip_if: sunday`);
   long-way's Saturday Anki obviously only fired Saturdays. Proposed common
   Anki = daily Mon–Sat. Confirm Sunday stays a true rest day for SRS too.
2. **A or B?** First-class bundle (clean, ~5 files of engine work) vs minimal
   dummy syllabus (ships now, ugly card). Owner's call.
3. **Should the global SRS streak replace, or sit alongside, the
   per-curriculum streaks on the dashboard?** Proposed: alongside — one
   "SRS" streak at the top, plus each curriculum's study streak.
