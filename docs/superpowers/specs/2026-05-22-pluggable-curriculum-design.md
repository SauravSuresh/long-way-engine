# Pluggable curriculum — design

**Status:** approved
**Date:** 2026-05-22
**Author:** PrevizKompany (with Claude)

## Problem

The Long Way curriculum is split across three coupled sources:

- `the-long-way.md` — prose curriculum, regex-parsed by `src/syllabus.py`
- `src/syllabus.py` — hardcoded `PRIMARY_BOOK_BY_MONTH` dict (months 1..39)
- `task_templates/modules.yaml` — 23 module onboarding tasks

Phase count (4), month count (39), and module count (23) are baked into
`dashboard.py`, `scheduler.py`, and `state.py` implicitly. Forking the
repo to run a different curriculum requires editing Python code, the
markdown narrative, and seven YAML files — and there is no documentation
for how to do this coherently.

## Goal

1. Move all forker-editable content out of Python code and into a single
   `curriculum/` directory.
2. Support arbitrary phase count, month count, and module count — the
   engine derives all shape from YAML.
3. Preserve the owner's progress byte-identically: same `state.yaml`,
   same Todoist cache keys, same task set fires on any given date.
4. Ship `AGENTS.md` so an AI agent can interview a forker and produce a
   complete curriculum bundle.
5. Ship 1–2 example curricula so forkers have a starting point.

## Non-goals

- New cadences. The six existing cadences (`daily`, `weekly`, `monthly`,
  `quarterly`, `annual`, `once-per-module`) stay code-defined. Forkers
  can author any number of templates of existing cadences but cannot
  add new cadence types without a code change. (YAGNI; lift later.)
- Runtime curriculum reloading. Load once at startup. Restart to swap.
- Multi-curriculum support. One active curriculum per repo checkout.

## Architecture

### File layout

```
long-way-engine/
├── src/                          # engine (no curriculum data)
│   ├── syllabus.py               # YAML loader, no regex/dict
│   ├── scheduler.py              # reads templates from curriculum dir
│   ├── dashboard.py              # derives counts from YAML
│   ├── curriculum_validator.py   # NEW — fail-fast validation
│   └── ...                       # unchanged
│
├── curriculum/                   # active curriculum (forker edits)
│   ├── syllabus.yaml             # phases, months, modules, books
│   ├── manifest.yaml             # ritual_times + placeholders declared
│   ├── modules.yaml              # module trunk tasks (moved)
│   ├── rituals/
│   │   ├── daily.yaml            # moved from task_templates/
│   │   ├── weekly.yaml
│   │   ├── monthly.yaml
│   │   ├── quarterly.yaml
│   │   ├── annual.yaml
│   │   └── practices.yaml
│   └── reflection_templates/     # moved
│       ├── weekly.md
│       ├── monthly.md
│       ├── quarterly.md
│       └── annual.md
│
├── examples/                     # starter curricula
│   ├── ml-engineer-12mo/
│   └── frontend-craft-6mo/
│
├── the-long-way.md               # owner prose, untouched, not parsed
├── config.yaml                   # gains `curriculum_dir: curriculum`
├── state.yaml                    # UNCHANGED
└── AGENTS.md                     # AI agent guide
```

### Pluggable boundary

| Surface | Defined in | Forker edits? |
| --- | --- | --- |
| Phase count, names, month ranges | `curriculum/syllabus.yaml` | yes |
| Books, authors, month spans | `curriculum/syllabus.yaml` | yes |
| Primary book per month | `curriculum/syllabus.yaml` | yes |
| Module list (number, name, phase) | `curriculum/syllabus.yaml` | yes |
| Module onboarding tasks | `curriculum/modules.yaml` | yes |
| Daily/weekly/.../practice templates | `curriculum/rituals/*.yaml` | yes |
| Reflection markdown stubs | `curriculum/reflection_templates/*.md` | yes |
| Required ritual_time slots | `curriculum/manifest.yaml` | yes |
| Cadence semantics (daily/weekly/...) | `src/scheduler.py` | no — code change |
| Skip-rule vocabulary (sunday, pair_day, ...) | `src/scheduler.py` | no — code change |
| Placeholder substitution | `src/templates.py` | no — code change |

## Schemas

### `curriculum/syllabus.yaml`

```yaml
meta:
  name: "The Long Way"
  total_months: 39          # optional; derived from phases if omitted
  start_month_index: 1      # almost always 1

phases:
  - number: 1
    name: "Foundations"
    months: [1, 12]         # inclusive, 1-indexed
  - number: 2
    name: "Go & the Backend Toolkit"
    months: [13, 20]
  # ... any number of phases

books:
  - title: "Computer Systems: A Programmer's Perspective"
    author: "Bryant & O'Hallaron"
    phase: 1
    months: [1, 6]          # inclusive; null/omitted for reference-only
    role: primary           # primary | secondary | reference
  - title: "Debugging"
    author: "David Agans"
    phase: 1
    months: [2, 2]
    role: secondary
  # ... etc

primary_book_by_month:
  1: "Computer Systems: A Programmer's Perspective"
  2: "Computer Systems: A Programmer's Perspective"
  # ... explicit entries; gaps carry forward from prior month
  39: "Designing Data-Intensive Applications"

modules:
  - number: 1
    name: "Python Basics"
    phase: 1
    estimated_hours: 60     # optional, dashboard-only
  - number: 2
    name: "Debugging (Agans)"
    phase: 1
    estimated_hours: 10
  # ... dense 1..N, no gaps
```

### `curriculum/manifest.yaml`

```yaml
ritual_times_required:
  - morning_reading
  - anki
  - evening_hands_on
  - friday_review
  - saturday_deep_block
  - sunday_trace

placeholders_used:
  - current_book
  - current_module
  - iso_year
  - iso_week
  - year
  - month
  - quarter

config_flags:
  pair_day: thursday        # default; forker may override in config.yaml
  sunday_off: true
```

### `curriculum/rituals/*.yaml`

Schema identical to current `task_templates/*.yaml`. Fields: `id`,
`title`, `description`, `due`, `labels`, `cadence`, `skip_if`,
`day_of_week` (weekly), `day_of_month` (monthly), `module_number`
(once-per-module), `reflection.create_stub` + `reflection.stub_path`.

Cadence vocabulary: `daily`, `weekly`, `monthly`, `quarterly`, `annual`,
`once-per-module`. Skip-rule vocabulary: `sunday`, `pair_day`,
`last-saturday-of-month`.

### `curriculum/modules.yaml`

Schema identical to current `task_templates/modules.yaml`. Onboarding
task per module, lineage-detour tasks for flagged ancestor reads. Join
to syllabus by `module_number`.

### `curriculum/reflection_templates/*.md`

Markdown templates with `{date}`/`{week}`/`{year}`/`{month}` placeholder
interpolation. No schema change.

## Engine changes

### `src/syllabus.py`

- Delete `_PHASE_SECTION_RE`, `_BOOK_RE`, `_MONTHS_RE`.
- Delete `parse_books()`, `parse_books_from_file()`.
- Delete `PRIMARY_BOOK_BY_MONTH` dict.
- Add `Syllabus` dataclass: `phases`, `books`, `primary_book_by_month`,
  `modules`, `meta`.
- Add `load_syllabus(curriculum_dir: Path) -> Syllabus`.
- `current_book(month, syllabus)` — table lookup with carry-forward,
  takes syllabus as parameter.

### `src/config.py`

- `Config` gains `curriculum_dir: Path` field, default `Path("curriculum")`.
- `load_config()` reads optional `curriculum_dir` from `config.yaml`.

### `src/scheduler.py`

- Template loader reads from `config.curriculum_dir / "rituals" / *.yaml`
  and `config.curriculum_dir / "modules.yaml"`.
- Cadence dispatch unchanged.
- Skip-rule logic unchanged.

### `src/dashboard.py`

- Replace hardcoded `4` (phases) with `len(syllabus.phases)`.
- Replace hardcoded `39` (months) with `max(syllabus.primary_book_by_month)`.
- Replace hardcoded `23` (modules) with `len(syllabus.modules)`.
- Phase tree iterates `syllabus.phases` instead of literal list.
- Per-phase reading list comes from `[b for b in syllabus.books if
  b.phase == p.number]`.

### `src/state.py`

- No new validation added here. Validator (check 7) cross-checks state
  against syllabus at startup. `state.py` itself remains a pure
  load/save of the state document.

### `src/main.py`

- Call `load_syllabus(config.curriculum_dir)` once at startup.
- Pass syllabus through to scheduler, dashboard, current_book resolution.

### `src/curriculum_validator.py` (new)

Single entry point: `validate(curriculum_dir: Path, state: State,
config: Config) -> None`. Raises `CurriculumError` with all violations
aggregated into one message.

Checks:

1. Every `primary_book_by_month` value exactly matches some
   `books[].title`.
2. `phases[*].months` ranges, when sorted by `phases[].number`, form a
   non-overlapping sequence with no gaps (each phase's `months[0]`
   equals the previous phase's `months[1] + 1`, and `phases[0].months[0]`
   equals `meta.start_month_index`).
3. Every `modules[].phase` matches an existing `phases[].number`.
4. `modules[].number` is dense from 1..N (no gaps, no duplicates).
5. Every `modules.yaml` task's `module_number` exists in
   `syllabus.modules`, AND every `syllabus.modules[].number` has at
   least one task in `modules.yaml` with `cadence: once-per-module`
   (the onboarding task). Additional `once-per-module` tasks per
   module (e.g., lineage detours) are allowed.
6. Every `manifest.ritual_times_required` entry exists in
   `config.ritual_times`.
7. `state.current_module <= len(modules)` and `state.month <=
   max(primary_book_by_month)`.
8. Every `cadence` in `rituals/*.yaml` is in the set
   `{daily, weekly, monthly, quarterly, annual, once-per-module}`.
9. Every `skip_if` value is in the set
   `{sunday, pair_day, last-saturday-of-month}`.
10. Every template `id` in `rituals/*.yaml` and `modules.yaml` is
    unique across the whole curriculum.

Called once at startup, before any task generation.

## Migration plan

Single PR, zero behavior change for the owner.

1. **Move files** — `git mv`:
   - `task_templates/{daily,weekly,monthly,quarterly,annual,practices}.yaml`
     → `curriculum/rituals/`
   - `task_templates/modules.yaml` → `curriculum/modules.yaml`
   - `reflection_templates/` → `curriculum/reflection_templates/`
2. **Generate `curriculum/syllabus.yaml`** via one-time conversion script
   (`scripts/migrate_syllabus.py`, deleted after merge). Reads existing
   `PRIMARY_BOOK_BY_MONTH` and runs the existing regex over
   `the-long-way.md`. Owner eyeballs the diff before committing.
3. **Hand-author `curriculum/manifest.yaml`** (~15 lines).
4. **Code changes** per "Engine changes" section above.
5. **Author examples** — `examples/ml-engineer-12mo/` and
   `examples/frontend-craft-6mo/`. Each ships a complete `curriculum/`
   bundle, validated in CI.
6. **Write `AGENTS.md`** per Section 5 of the brainstorm transcript
   (outline reproduced below in this doc).
7. **Update `README.md`** with a "Fork it for your own curriculum"
   section pointing at `AGENTS.md`.

Owner's `state.yaml`, `cache.json`, all existing template IDs stay
byte-identical. Todoist cache dedupe keys keep working — no historical
task re-fires.

## `AGENTS.md` outline

```
1. What this engine does
2. File layout you will produce
3. Schema reference
   - syllabus.yaml
   - manifest.yaml
   - rituals/*.yaml
   - modules.yaml
   - reflection_templates/*.md
4. Validation rules the engine enforces
5. Interview protocol (run end-to-end on request)
   Step 1 — Goal & duration
   Step 2 — Phase split
   Step 3 — Books / primary resource per month
   Step 4 — Modules
   Step 5 — Rituals (recommended skeleton: daily morning study + SRS +
            evening build; weekly retrieval + deep block + practice;
            monthly write-up + retrieval + retro; quarterly synthesis;
            annual review)
   Step 6 — Practices (optional)
   Step 7 — Write files, run validator, dry-run
6. Anti-patterns
   - No artifact = no learning week
   - Cap modules per phase at ~8
   - Don't invent cadences
   - Carry-forward is fine — not every month needs a unique primary book
7. Examples
   - examples/ml-engineer-12mo/
   - examples/frontend-craft-6mo/
```

## Testing strategy

- **Golden-output test (the acceptance test).** Before refactor:
  capture `python -m src.main --dry-run --date <D>` for a battery of
  dates spanning every cadence and skip-rule edge case:
  - A regular weekday (e.g., Tuesday)
  - A Friday (weekly review fires)
  - A Saturday (deep block fires)
  - A last-Saturday-of-month (monthly retrieval + review, deep block skipped)
  - A pair day (Thursday — evening hands-on skipped)
  - A Sunday (everything blocked)
  - January 1 (quarterly + annual fire)
  - April 1, July 1, October 1 (quarterly only)
  - A module-boundary date
  Captured outputs (task list + dashboard HTML) commit to
  `tests/golden/`. After refactor: same command on same dates must
  produce byte-identical output.
- **Validator unit tests.** Each fail-fast rule has a test with a
  broken fixture that should trip exactly that rule.
- **Example curricula tests.** Each `examples/*` directory loads,
  validates, and dry-runs for one date without crashing.
- **Existing tests.** `test_syllabus.py` rewritten to test YAML loader
  rather than regex/dict drift. `test_scheduler.py` and
  `test_dashboard.py` updated to inject a test syllabus fixture.

## Error handling

- **Load time:** fail fast with all violations aggregated into one
  error message. No partial loads.
- **Runtime:** trust validated data. No defensive checks against
  conditions the validator already enforces.
- **Forker UX:** validator error messages name the file, the field,
  and the expected vs actual value. Example:
  `curriculum/syllabus.yaml: primary_book_by_month[7] = "Networking"
  has no matching books[].title (closest match: "Computer Networking:
  A Top-Down Approach")`.

## Open questions

None at design time. Concrete example curricula content (the two
`examples/`) will be drafted during implementation; their exact
contents do not affect the engine design.
