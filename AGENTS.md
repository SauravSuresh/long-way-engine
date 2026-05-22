# AGENTS.md — Building a curriculum for long-way-engine

This file tells an AI agent how to help a user build a curriculum
bundle that the long-way-engine can run. If you are an AI invoked by
a user in a fork of this repo, read this end-to-end before producing
files.

---

## 1. What this engine does

`long-way-engine` turns a multi-month learning plan into Todoist tasks
and a dashboard. Every day it:

- Loads the active curriculum from `curriculum/` (path configurable
  via `config.yaml`'s `curriculum_dir` key).
- Reads `state.yaml` for the user's current phase, month, and module.
- Walks every template in `curriculum/rituals/*.yaml` and
  `curriculum/modules.yaml`, decides which fire today based on cadence
  rules, resolves placeholder variables, and creates Todoist tasks
  (deduped via a local cache).
- Renders a static HTML dashboard from state + completion data.

Three pieces are pluggable; two are not.

**Pluggable (forker edits):**

- `curriculum/syllabus.yaml` — phases, months, books, modules
- `curriculum/rituals/*.yaml` — daily/weekly/monthly/quarterly/annual
  ritual + practice templates
- `curriculum/modules.yaml` — module onboarding tasks + lineage detours
- `curriculum/reflection_templates/*.md` — reflection stub templates
- `curriculum/manifest.yaml` — declares which ritual_times and
  placeholders the bundle needs

**Not pluggable (engine code defines):**

- Cadence vocabulary: `daily`, `weekly`, `monthly`, `quarterly`,
  `annual`, `once-per-module`
- Skip-rule vocabulary: `sunday`, `pair_day`, `last-saturday-of-month`
- Placeholder substitution syntax: `{current_book}`,
  `{ritual_times.X}`, `{iso_year}-W{iso_week:02d}`, `{year}`, `{month}`,
  `{quarter}`, `{current_module}`

---

## 2. File layout you will produce

```
curriculum/
├── syllabus.yaml
├── manifest.yaml
├── modules.yaml
├── rituals/
│   ├── daily.yaml
│   ├── weekly.yaml
│   ├── monthly.yaml
│   ├── quarterly.yaml
│   ├── annual.yaml
│   └── practices.yaml
└── reflection_templates/
    ├── weekly.md
    ├── monthly.md
    ├── quarterly.md
    └── annual.md
```

Required files: `syllabus.yaml`, `manifest.yaml`, `modules.yaml`, at
least one ritual yaml. Reflection templates are optional but
recommended.

---

## 3. Schema reference

### `syllabus.yaml`

```yaml
meta:
  name: string                     # display name
  total_months: int                # optional; derived from phases if omitted
  start_month_index: 1             # almost always 1

phases:
  - number: int                    # dense 1..N
    name: string
    months: [start, end]           # inclusive, contiguous across phases

books:
  - title: string                  # must match primary_book_by_month values
    author: string
    phase: int                     # must reference an existing phase
    months: [start, end]           # optional; omit for reference-only
    role: primary|secondary|reference

primary_book_by_month:
  1: "Book Title"                  # title must exist in books[]
  2: "Book Title"
  # gaps are OK — engine carries forward from prior month

modules:
  - number: int                    # dense 1..N, no gaps
    name: string
    phase: int                     # must reference an existing phase
    estimated_hours: int           # optional, dashboard-only
```

### `manifest.yaml`

```yaml
ritual_times_required:
  - morning_reading                # must exist in config.yaml ritual_times
  - evening_hands_on
  # ... etc

placeholders_used:
  - current_book
  - current_module
  - iso_year
  # ... etc — informational, not validated

config_flags:
  pair_day: thursday               # default; user overrides in config.yaml
  sunday_off: true
```

### `rituals/*.yaml`

Each file is a YAML list of templates. A template:

```yaml
- id: string                       # unique across the entire curriculum
  title: string                    # with placeholders like {current_book}
  description: |
    Multi-line. Same placeholder rules as title.
  due: "today at {ritual_times.morning_reading}"
  labels: [list, of, strings]
  cadence: daily|weekly|monthly|quarterly|annual|once-per-module
  skip_if:                         # optional; rules ANDed
    - sunday                       # global rest day
    - pair_day                     # config.pair_day weekday
    - last-saturday-of-month       # last Saturday of current month
  day_of_week: monday              # required for cadence: weekly
  day_of_month: 1                  # required for cadence: monthly
                                   # may be int 1..28, "last-day",
                                   # or "last-saturday"
  module_number: int               # required for cadence: once-per-module
  reflection:                      # optional
    create_stub: true
    stub_path: "reflections/weekly/{iso_year}-W{iso_week:02d}.md"
```

### `modules.yaml`

Same schema as rituals/*.yaml, but every entry has
`cadence: once-per-module` and a `module_number`. Each module in
syllabus.modules must have at least one onboarding task here. Multiple
tasks per module_number are allowed (e.g., lineage detours that fire
on the same module advance).

### `reflection_templates/*.md`

Markdown templates with `{date}`, `{week}`, `{year}`, `{month}`,
`{quarter}` placeholders. Loaded when a ritual template with
`reflection.create_stub: true` fires.

---

## 4. Validation rules the engine enforces at startup

`src/curriculum_validator.py` runs these checks. Failure aggregates
every violation into a single error message.

1. Every `primary_book_by_month` value exactly matches some
   `books[].title`.
2. `phases[*].months` are contiguous with no gaps; phase 1 starts at
   `meta.start_month_index`.
3. Every `modules[].phase` references an existing `phases[].number`.
4. `modules[].number` is dense 1..N with no gaps and no duplicates.
5. Every `syllabus.modules[].number` has at least one
   `cadence: once-per-module` task in `modules.yaml`.
6. Every `manifest.ritual_times_required` entry exists in
   `config.yaml`'s `ritual_times`.
7. `state.current_module <= len(modules)` and `state.month <=
   max(primary_book_by_month)`.
8. Every `cadence` value is in the supported set.
9. Every `skip_if` rule is in the supported vocabulary.
10. Every template `id` is unique across the curriculum.

---

## 5. Interview protocol

When a user says "help me build a curriculum", run these seven steps.
Ask one question at a time. Confirm before moving on.

**Step 1 — Goal & duration.** Ask: "What are you trying to be able
to do, and over what time horizon?" Probe for concrete outcomes
("a deployable thing", not "understand X"). Pin a total month count.
Don't accept "a year-ish" — pick a number.

**Step 2 — Phase split.** Propose 2–4 phases that sequence skills.
Each phase ends with a demonstrable capability ("can write a basic
Go HTTP server", not "knows about Go"). Phases should be contiguous
month ranges. Confirm.

**Step 3 — Books / primary resources per month.** For each month,
pick ONE primary resource — usually a book, sometimes a course or a
project. Carry-forward is fine: if months 11–12 are project-only
with no new book, don't add entries for them; the engine carries
the month 10 entry forward.

**Step 4 — Modules.** Within each phase, define 2–8 modules
(~2–6 weeks each). Modules are discrete units the user advances
through one at a time (`state.current_module` only goes up). Give
each a `name` and an `estimated_hours`. Author one onboarding task
per module in `modules.yaml`.

**Step 5 — Rituals.** Use this skeleton. The two rows marked
**required** must appear in every curriculum you generate, regardless
of the user's domain. The rest are recommended but flexible.

| Cadence | Ritual | Status |
|---|---|---|
| daily | spaced-repetition review (~10–15 min) | **REQUIRED** |
| daily | morning study (~30 min) | **REQUIRED** |
| daily | evening hands-on (~60–90 min) | recommended |
| weekly | end-of-week retrieval (~20 min) | recommended |
| weekly | deep block (~3–4 hours) | recommended |
| weekly | one active practice (rotates) | recommended |
| monthly | public write-up (1st of month) | recommended |
| monthly | retrieval (last Saturday) | recommended |
| monthly | retrospective (last Saturday) | recommended |
| quarterly | synthesis essay | recommended |
| annual | full review + plan revision | recommended |

**Why spaced-repetition is required.** Long-horizon learning fails
without retention reinforcement. Whatever the user is studying — code,
math, history, languages, medicine — they will forget 80% of it within
a month unless they review it on a spaced schedule. The daily SRS
ritual is the single highest-leverage habit in the entire system; a
curriculum without it ships a hole at the foundation. Default to
Anki; mention SuperMemo, Mochi, RemNote, or paper-card systems if the
user pushes back on Anki specifically, but don't drop the cadence.

A sample SRS template (adapt the time slot, adjust the description
to the user's domain):

```yaml
- id: daily-srs-review
  title: "Spaced-repetition review (Anki)"
  description: |
    10–15 min. Whenever — commute, lunch, before bed. Add 3–5 new
    cards per day from what you read and built. No more.
  due: "today at {ritual_times.srs_review}"
  labels: [daily-ritual]
  cadence: daily
  skip_if: sunday
```

Add `srs_review` (or equivalent) to `manifest.ritual_times_required`
and to `config.yaml`'s `ritual_times`.

**Why morning study is required.** Front-loading deep work before
the day's distractions arrive is the second-most reliable habit in
sustained-learning research. The "morning study" ritual binds a
fixed time + a paper book + a paper notebook, and it's what populates
`{current_book}` from the syllabus.

Map every other ritual you generate to a `ritual_times` slot in
`config.yaml`. Add those slot names to `manifest.ritual_times_required`.

**If the user objects to either required ritual:** push back once,
quoting the reasoning above. If they still refuse, document the
omission in a comment at the top of `rituals/daily.yaml` so the
gap is visible. Do not silently skip it.

**Step 6 — Practices (optional).** Weekly cadence templates that
aren't routine — deliberate skill drills like "trace one system
end-to-end", "read real code", "pair with a senior". Use
`day_of_week` to spread them across the week so they don't all land
on Saturday.

**Step 7 — Write files, run validator, dry-run.** Produce all YAML
files. Run:

```bash
python -c "
from pathlib import Path
from src.curriculum_validator import validate
from src.config import load_config
from src.state import load_state
cfg = load_config(Path('config.yaml'), Path('.env'))
st = load_state(Path('state.yaml'))
validate(Path('curriculum'), ritual_times=cfg.ritual_times,
         state_current_module=st.current_module, state_month=st.month)
print('OK')
"
```

Fix every error until validator prints `OK`. Then:

```bash
python -m src.main --dry-run --today $(date +%Y-%m-%d)
```

Confirm a sensible task set fires for today. Done.

---

## 6. Anti-patterns

- **Skipping the daily SRS ritual.** This is the most common
  failure mode and the most expensive. Without spaced repetition,
  retention collapses inside a month and a 12-month plan delivers
  ~3 months of durable learning. Always include it. See Step 5.
- **No artifact = no learning week.** A week of pure reading without
  a writeup, a commit, or a public note is forgotten. Every weekly
  ritual should produce something.
- **More than ~8 modules per phase.** If you need more, it's two
  phases.
- **Inventing cadences.** Don't author `every_other_wednesday`. Use
  what exists. Open an issue if a real new cadence is needed.
- **One primary book per unique month.** Carry-forward is the
  point. Long books span many months. Sparse `primary_book_by_month`
  is correct.
- **Templates without an `id`.** Always set one. Engine uses it as
  the Todoist dedupe key.

---

## 7. Examples

- `examples/ml-engineer-12mo/` — 12-month ML engineer path, 3 phases,
  ~9 modules
- `examples/frontend-craft-6mo/` — 6-month frontend deep-dive, 2
  phases, ~6 modules

Both validate cleanly via `python -m src.curriculum_validator`. Copy
one as a starting point.
