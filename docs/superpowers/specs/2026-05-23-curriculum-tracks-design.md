# Curriculum-declared tracks + gated templates — design

**Status:** approved (design locked; implementation TBD)
**Date:** 2026-05-23
**Branch:** TBD (proposed: `curriculum-tracks`)
**Author:** PrevizKompany (with Claude)
**Companion spec:** [`2026-05-23-state-review-todoist-design.md`](./2026-05-23-state-review-todoist-design.md) (Pattern B, merged)

## Problem

Courses (boot.dev, CS50, Neuromatch), certifications (LFCS, AWS
SAA), active branches ("Text editor in C"), and lineage detours
are real curriculum content. They drive work. Some span months;
some span years. Today the engine handles them inconsistently:

1. **Auto-onboarding tasks** fire only for modules. A learning
   track in `state.yaml` produces no Todoist task — the owner does
   the work inside the catch-all `evening-hands-on` slot or in
   manually-created Todoist tasks outside the engine.
2. **`state.yaml`'s `learning_tracks` is owner-authored** with
   "arbitrary owner-defined categories." A typo in `Lineage
   detours` silently creates a new category. No single source of
   truth says "boot.dev is part of this curriculum."
3. **Ritual templates can't gate on track state.** If a template
   should fire only while a course is in progress, the only way
   to stop it when the course completes is to hand-edit
   `rituals/*.yaml`.

The architectural mismatch: `syllabus.yaml` declares phases,
books, and modules; `state.yaml` declares learning tracks. The
curriculum bundle does not describe the whole plan — half of it
lives in the state file and is unvalidated.

> "Ideally the curriculum should describe everything." — owner

## Goal

Pull tracks into the curriculum schema as a first-class
declarative surface, with opt-in lifecycle and gateable templates:

1. `curriculum/syllabus.yaml` gains a `tracks:` section listing
   every track the curriculum acknowledges.
2. The validator rejects `state.yaml` `learning_tracks` entries
   that don't match a declaration. Typos become fail-fast errors.
3. Ritual templates gain a `gated_by:` field (tagged union) that
   ANDs additional predicates onto cadence dispatch — track-state
   gates and module-state gates.
4. Declarations with `months: [start, end]` opt into automatic
   lifecycle (`not_started → current → done` at month
   boundaries). Declarations without `months` stay
   owner-controlled.
5. State-review sub-task vocabulary gains `mark_track_started` /
   `mark_track_finished`. The Sunday review parent **auto-injects**
   one finish-checkbox per `current` track at parent-creation
   time, so the owner doesn't need to author one sub-task per
   declaration.

After this lands, every scheduled task — module work, ritual,
course session, cert prep — is described in `curriculum/`.
Nothing in `state.yaml` drives scheduling; state stores only
positions.

## Backward-compatibility constraint (hard)

**The owner's current state and current daily-cron output must
not change on merge.** Specifically:

- `state.yaml` is not edited by this change.
- No template that fires today stops firing tomorrow.
- No new template fires that didn't fire today.
- `tests/golden/*.json` must keep passing byte-for-byte.
- `state_log.yaml` gains no entries on the first cron after merge.

The implementation PR satisfies this by:

1. Adding a `tracks:` section to `curriculum/syllabus.yaml`
   that declares every entry currently in
   `state.yaml.learning_tracks` (today: `Courses: "boot.dev
   backend path"`). All declarations land **without `months:`**
   so the lifecycle is fully manual.
2. Adding **no** `gated_by:` to any existing ritual template.
   The owner adds them incrementally as they want gating.
3. Auto-injection of finish-checkboxes only takes effect at the
   NEXT weekly-state-review creation; the currently open review
   parent (if any) is unchanged.

Adoption is opt-in per declaration and per template.

## Non-goals

- **Track DAGs.** No `depends_on` between tracks.
- **Per-track ritual times.** `gated_by` chooses whether a
  template fires; existing `due` / `ritual_times.X` decides when.
- **Track-specific reflection cadences.** Reuse existing weekly /
  monthly reflection rituals.
- **A `skipped` lifecycle state.** Owner's existing state always
  wins; out-of-range auto-transitions no-op. See "Auto-lifecycle
  conflict rules" below.

## Architecture

### New / modified files

```
src/
├── tracks.py                  # new: load + lifecycle + gate predicates
├── scheduler.py               # modified: gated_by predicate
├── syllabus.py                # modified: parse `tracks:` section
├── state_review.py            # modified: lifecycle phase + auto-inject finish sub-tasks
├── state_mutations.py         # modified: mark_track_started/finished handlers
├── curriculum_validator.py    # modified: rules 14-18
├── templates.py               # modified: Template.gated_by field
├── main.py                    # modified: lifecycle phase invocation order
├── dashboard.py               # modified: tracks section from curriculum
curriculum/
├── syllabus.yaml              # modified: top-level tracks: list
└── rituals/*.yaml             # forker may add optional gated_by per template
```

### Daily cron flow (updated)

```
1. Load config + state + syllabus, validate curriculum.
2. STATE-MUTATION PHASE (Pattern B, already shipped):
   a. Read weekly-state-review sub-tasks; apply.
   b. Read persistent emergency-pause / resume; apply.
   c. Auto-unpause if paused_until elapsed.
3. TRACK-LIFECYCLE PHASE (new):
   - For each declaration with months: compute expected state from
     derived_month. Apply transitions per the conflict rules below.
     Each transition's log entry uses task_id
     `auto-track-<slug>-<start|end>-<month>`.
4. TASK-CREATION PHASE (existing):
   - Every template's gated_by predicates evaluated against
     post-lifecycle state. Gated-off templates skip with reason
     `SKIP (gated: <reason>)`.
   - For state_review templates, parent creation triggers (a) the
     curriculum-authored sub-tasks and (b) one auto-injected
     `mark_track_finished` sub-task per `current` track.
5. DASHBOARD PHASE (existing): regenerate docs/index.html.
```

### Pluggable boundary

| Surface | Defined in | Forker edits? |
| --- | --- | --- |
| Track declarations | `curriculum/syllabus.yaml` `tracks:` | yes |
| Allowed categories | implied by declarations | yes (per-curriculum) |
| `gated_by` on a template | `curriculum/rituals/*.yaml` | yes |
| Lifecycle vocabulary (not_started/current/done) | `src/state.py` (locked) | no |
| Auto-lifecycle impl | `src/tracks.py` | no |
| Gate predicate types | `src/scheduler.py` (locked vocabulary) | no |

## Schemas

### `syllabus.yaml`: new top-level `tracks:` list

```yaml
tracks:
  - title: "boot.dev backend path"
    category: Courses
    phase: 1
    # No months: -> owner-controlled lifecycle (manual via state-review).

  - title: "LFCS"
    category: Certifications
    phase: 1
    months: [9, 9]     # auto-current at month 9, auto-done at month 10.

  - title: "Module 6 detour: bytecode VM"
    category: Lineage detours
    phase: 1
    # No months: owner-controlled.
```

- `title` (required, unique across the section).
- `category` (required, free string; categories are the implicit
  union of every declaration's `category`).
- `phase` (required, must match an existing phase).
- `months` (optional `[start, end]`, both inclusive, both in
  `[1, max_month_in_phases]`, `start <= end`). Presence opts the
  track into auto-lifecycle; absence keeps it manual.

### Ritual template: new `gated_by:` field (tagged union)

```yaml
- id: weekly-bootdev-session
  title: "boot.dev session"
  due: "today at {ritual_times.evening_hands_on}"
  labels: [weekly-ritual, course]
  cadence: weekly
  day_of_week: tuesday
  gated_by:
    - { type: track, category: Courses, item: "boot.dev backend path", states: [current] }
    - { type: module_gte, value: 3 }   # only after module 3
```

A template's `gated_by` is a LIST. Every gate must pass (logical
AND) for the template to fire.

**Gate type vocabulary (locked):**

| `type` | Args | True when |
| --- | --- | --- |
| `track` | `category`, `item`, `states` (default `[current]`) | `state.learning_tracks[category].get(item) in states` |
| `module_eq` | `value` (int) | `state.current_module == value` |
| `module_gte` | `value` (int) | `state.current_module >= value` |
| `module_lte` | `value` (int) | `state.current_module <= value` |

Adding a new gate type requires a code change (per the
"no-vocabulary-invention-by-forkers" rule). Forkers compose
existing types; the engine never speculates.

`gated_by` is orthogonal to `skip_if`: both must pass.

### `state.yaml`: shape unchanged, validation tightened

```yaml
learning_tracks:
  Courses:
    "boot.dev backend path": current
```

Owner-edited shape stays the same. **Validator rule 14**: every
`(category, title)` pair in `state.learning_tracks` must exist as
a declaration in `syllabus.tracks`. Typos that previously
produced silent extra categories now fail fast.

### State-review sub-task vocabulary additions

| `type` | Args | Effect | Idempotent? |
| --- | --- | --- | --- |
| `mark_track_started` | `category`, `item` | `state.learning_tracks[category][item] = current`. Initializes the category dict if missing. | Per `todoist_task_id` |
| `mark_track_finished` | `category`, `item` | `state.learning_tracks[category][item] = done`. | Per `todoist_task_id` |

Auto-lifecycle uses synthetic `todoist_task_id`s:
- `auto-track-<slug>-start-<month>` (not_started → current)
- `auto-track-<slug>-end-<month>` (current → done)

`<slug>` is `category-title` lowercased with non-alphanumerics
replaced by `-`. Idempotency via Pattern B's per-task-id log
check.

### Auto-lifecycle conflict rules (the table)

For each declaration with `months: [start, end]`, the lifecycle
pass computes the *expected* state from `derive_month(today)`:

| derived_month | expected lifecycle position |
| --- | --- |
| `< start` | not yet — no transition |
| `start..end` | current |
| `> end` | done |

The transition the engine MAY apply:

| owner state | expected position | engine action |
| --- | --- | --- |
| not_started | not yet | no-op |
| not_started | current | apply `mark_track_started` |
| not_started | done | **no-op** (owner skipped the window; stays not_started) |
| current | not yet | no-op (owner started early — keep) |
| current | current | no-op |
| current | done | apply `mark_track_finished` |
| done | any | no-op (owner finished; never re-open) |

Rule: owner state always wins on a tie; engine only adds
forward-progress transitions whose preconditions match. Result:
no surprising state shifts at month boundaries.

Pause interaction: lifecycle pass is SKIPPED while `state.paused`
is true. After the auto-unpause cron (Pattern B), the lifecycle
pass runs on the post-unpause `derive_month`. If a window passed
entirely inside a pause window, the track stays at its
pre-pause state (per the table above — `not_started` past `end`
→ no-op).

### Auto-injected state-review sub-tasks

When the engine creates a weekly-state-review parent task and
iterates curriculum-authored `sub_tasks[]`, it then appends one
auto-injected sub-task per track currently in state `current`:

```
"I finished [<category>: <title>]"     action: mark_track_finished
```

The external_id of each auto-injected sub-task is hashed from
`(parent_ext_id, "auto-finish", category, title)` so the cache
dedupes across consecutive Sundays for the same `current` track.
When the track flips to `done` (whether via the auto-injected
sub-task itself or some other path), the next parent creation no
longer injects that sub-task.

Carve-out from Pattern B's "sub-task titles and arguments are
curriculum-author-defined" rule: auto-injection is the narrow
exception, justified because the set is per-track-INSTANCE not
per-curriculum-TEMPLATE, and authoring N sub-tasks for N tracks
is exactly the friction the curriculum-as-truth refactor exists
to remove.

### New placeholders

| Placeholder | Resolves to |
| --- | --- |
| `{track_title}` | The `item` of the firing template's first `gated_by` `track` gate. Used inside gated templates' title/description for natural prose. |

`{current_tracks}` (proposed in v1) DROPPED — no concrete use
case justified the complexity.

## Engine modules

### `src/tracks.py` (new)

```python
@dataclass(frozen=True)
class TrackDeclaration:
    title: str
    category: str
    phase: int
    months: tuple[int, int] | None


@dataclass(frozen=True)
class LifecycleTransition:
    category: str
    title: str
    from_state: str
    to_state: str
    todoist_task_id: str


def load_track_declarations(syllabus_dict: dict) -> list[TrackDeclaration]: ...

def slug_of(category: str, title: str) -> str: ...

def expected_position(decl: TrackDeclaration, derived_month: int) -> str:
    """Returns 'pre_start' | 'current' | 'past_end'."""

def compute_lifecycle_transitions(
    state: State,
    tracks: list[TrackDeclaration],
    derived_month: int,
    applied_task_ids: set[str],
) -> list[LifecycleTransition]:
    """Apply the conflict-rule table; emit transitions for what the
    engine should actually do. Caller routes each to the matching
    state_mutations handler."""

def evaluate_gates(template_gated_by: list[dict], state: State) -> tuple[bool, str | None]:
    """Returns (passes, skip_reason). Each gate is a tagged dict per
    the vocabulary in the spec. Locked-vocabulary dispatch."""
```

Pure functions; no IO; no syllabus mutation. Orchestrator routes
transitions to the existing `state_mutations.ACTION_HANDLERS`.

### `src/scheduler.py` changes

`should_create_today` gains one new check after the
`paused` / `sunday_off` (with state_review exemption) shorts:

```python
if template.gated_by:
    from src.tracks import evaluate_gates
    passes, reason = evaluate_gates(template.gated_by, state)
    if not passes:
        return False
```

Order: `paused` → `sunday_off` → `gated_by` → cadence dispatch.

### `src/templates.py` changes

`Template` and `ResolvedTemplate` gain:

```python
gated_by: list[dict[str, Any]] = field(default_factory=list)
```

Resolver gains `{track_title}` (lookup template.gated_by first
`type: track` entry's `item`).

### `src/syllabus.py` changes

Add `tracks: list[TrackDeclaration]` to the `Syllabus`
dataclass. `load_syllabus()` parses the new section permissively;
validator does the strict checks. Backward compat: missing
`tracks:` section parses as empty list.

### `src/state_mutations.py` changes

Two new handlers; added to `ACTION_HANDLERS`:

```python
def mark_track_started(state, *, category, item, todoist_task_id, today) -> MutationResult: ...
def mark_track_finished(state, *, category, item, todoist_task_id, today) -> MutationResult: ...
```

Both initialize `state.learning_tracks[category]` if absent.
`revert_last`'s prior-block restoration extends to handle a
`learning_tracks` key in the prior dict.

### `src/state_review.py` changes

`run_state_review_phase`:

- After auto-unpause, before the existing sub-task scan, run
  `compute_lifecycle_transitions(...)` and dispatch each via
  `mark_track_started` / `mark_track_finished` handlers.
- During the existing sub-task scan, dispatch new action types
  via the action-type dispatch (no orchestrator change needed).

`run()` in main.py extends parent-task creation: after creating
the curriculum-authored sub-tasks for a `state_review` template,
iterate `state.learning_tracks` and auto-inject one
`mark_track_finished` sub-task per `current` track.

## Validation rules (added to `curriculum_validator.py`)

Five new checks aggregate alongside the existing 13:

14. Every `(category, title)` pair in `state.learning_tracks`
    exists as a declaration in `syllabus.tracks`. (Validator
    receives the live state when invoked from main.py; the
    examples-validation test path passes no state and skips this
    rule.)
15. Every `tracks[].phase` references an existing phase.
16. If `tracks[].months` is present, both endpoints are in
    `[1, max_month_in_phases]`, with `start <= end`.
17. Every `gated_by[*].type` is in the locked vocabulary
    (`track`, `module_eq`, `module_gte`, `module_lte`).
18. For every `gated_by[*]` with `type: track`, the
    `(category, item)` pair resolves to a declared track; if
    `states` is present, every value is in
    `{not_started, current, done}`.

Rules 14 and 18 share a "category+title resolution" helper.

## Idempotency strategy

Reuses Pattern B's per-`todoist_task_id` log check. The auto-
lifecycle's synthetic ids encode `(category, title, side, month)`
so each transition appears at most once across replays. The
auto-injected `mark_track_finished` sub-tasks get content-marker
external_ids from `(parent_ext_id, "auto-finish", category,
title)`; same parent + same track produces the same id week
after week, only the parent's date varies (so the cache key
varies, and a fresh sub-task fires each week the track is still
`current`).

If `state_log.yaml` is wiped (e.g., `git checkout` accident),
auto-lifecycle replays every transition that should have fired
since `start_date`. Each replay applies via the conflict-rule
table; net effect is the engine re-establishing the "right"
state from `derive_month(today)`. Same recovery semantics as
Pattern B.

## Failure modes

- **Track declared in syllabus, never referenced in state.**
  Allowed — stays `not_started`. No error. The dashboard shows
  the declaration; absence in state.yaml renders as
  `not_started`.
- **Two declarations with same `(category, title)`.** Validator
  error (rule 15 expansion).
- **Template's `gated_by` references a track that doesn't
  exist.** Validator rule 18 catches at startup. Runtime can
  treat as "always false" defensively (dead-code path).
- **Owner manually flips a track via `state.yaml` edit during a
  lifecycle window.** Owner state wins; next cron's lifecycle
  pass no-ops (per the conflict table). The audit shows no
  transition, which is correct — owner did the transition by
  hand.
- **Empty `learning_tracks` dict + `current` tracks declared with
  months in the curriculum.** Next cron's lifecycle creates the
  category dict and applies `mark_track_started` — same effect
  as if owner had done it via state-review. Log entry uses the
  synthetic auto-id.

## Testing strategy

- **Unit tests for `expected_position` and
  `compute_lifecycle_transitions`**: parametrize across pre /
  in-range / post-range × owner states × prior-applied
  combinations.
- **Unit tests for `evaluate_gates`**: each gate type, ANDed
  combinations, missing track / missing category.
- **Unit tests for new state_mutations handlers**.
- **Validator tests for rules 14-18**: broken fixtures per rule.
- **Scheduler integration test**: gated template with
  module-gate AND track-gate; flip state between runs; verify
  fire/skip transitions.
- **End-to-end (mocked TodoistReviewClient)**: simulate a
  Sunday review crossing a month boundary; assert lifecycle
  transition AND owner sub-task both applied in one run, in
  log entry order matching the spec's phase ordering.
- **Auto-inject test**: weekly-state-review parent creation
  with two tracks currently `current` produces 2 extra
  sub-tasks beyond the curriculum-authored set; their
  external_ids are stable across re-runs (cache dedup).
- **Backward-compat smoke**:
  - `tests/golden/*.json` re-run unmodified after the live
    `curriculum/syllabus.yaml` gains the boot.dev declaration
    (no `months:`). Goldens must NOT diff — the new template
    fields (gated_by) are absent on all existing templates and
    the lifecycle pass no-ops without `months:`.
  - `state_log.yaml` after first cron post-merge: empty
    (or no new entries beyond what Pattern B would write).
  - Existing tests in `test_state.py`, `test_scheduler.py`,
    `test_state_review.py` keep passing without modification.

## Migration

For the OWNER (this repo):

1. PR adds a `tracks:` section to
   `curriculum/syllabus.yaml` containing exactly the entries
   currently in `state.yaml.learning_tracks`. Today: one entry,
   no `months:`. State.yaml: unchanged.
2. No new `gated_by:` on existing templates. The owner adds gates
   incrementally when they want them.
3. First cron after merge: validator passes (rule 14 ✓);
   lifecycle pass no-ops (no `months:` anywhere); scheduler
   doesn't change any template's fire/skip outcome (no
   `gated_by:` anywhere); auto-inject adds one
   `mark_track_finished` sub-task ("I finished [Courses:
   boot.dev backend path]") to the next weekly-state-review
   parent created — visible new sub-task in Todoist on the next
   Sunday creation, but ZERO Todoist tasks consumed or removed
   on the merge day itself.

For FORKERS using examples:

- The implementation PR adds `tracks: []` (empty list) to each
  example's `syllabus.yaml` so the schema field exists and the
  validator accepts the bundle. Examples can optionally add real
  declarations later in their own follow-up.
- AGENTS.md gains a new interview step 5.75 ("Parallel tracks")
  that asks about courses / certs / branches and authors a
  `tracks:` section.

## Implementation order

1. Schema + parsing + validator rules (no behavior change).
2. `gated_by` plumbing in templates + scheduler (no live
   template uses it yet).
3. State mutation handlers + state-review dispatch.
4. Auto-lifecycle pass (with `months:`).
5. Auto-injected sub-tasks.
6. Live migration: add boot.dev declaration to live
   `syllabus.yaml`. Single small commit; goldens unchanged.
7. AGENTS.md / FORKING.md / README.md doc updates.

Each step is mergeable on its own and breaks no existing test.

## Open questions resolved from draft

- **Predicate unification**: tagged-union LIST under `gated_by`,
  AND-composed. Module gates and track gates share the same field
  with discriminated `type`.
- **Auto-lifecycle conflicts**: explicit table; owner always
  wins; out-of-range stays put; no `skipped` lifecycle state.
- **State-review sub-task ergonomics**: engine auto-injects one
  finish-checkbox per `current` track. Narrow carve-out from the
  curriculum-authored rule.
- **`role:` field on track declarations**: dropped (no consumer
  in engine; symmetry with modules which also lack `role`).
- **Naming collision**: `syllabus.tracks` (declarations) vs
  `state.learning_tracks` (positions). Distinct field names; no
  rename needed in `state.yaml`, so no fork breakage.
- **Module gating**: in scope, ships in same change.
- **`{current_tracks}` placeholder**: dropped (no use case).
- **Once-per-track cadence**: deferred. `gated_by` on weekly
  cadence covers the common case.
- **Auto-onboarding task on track start**: no. Owner gets an
  auto-`mark_track_started` log entry; that's enough signal.

## Open questions remaining

1. **Should `tracks:` declarations be authored in their own file
   (`curriculum/tracks.yaml`) instead of nested under
   `syllabus.yaml`?** Modules currently live in `syllabus.yaml`
   too, so nesting is consistent. **Recommendation:** keep
   nested under syllabus. Easy to extract later if the section
   grows.
2. **Should the auto-injected sub-task title be customizable?**
   E.g., a curriculum-level template string. **Recommendation:**
   no — fixed format `"I finished [<category>: <title>]"` keeps
   the engine predictable. Forkers who want different wording
   author their own curriculum-authored sub-task and don't rely
   on auto-injection (the engine still auto-injects, producing
   two finish-checkboxes; harmless duplication).
