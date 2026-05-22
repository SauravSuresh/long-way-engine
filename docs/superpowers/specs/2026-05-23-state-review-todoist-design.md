# State review via Todoist (Pattern B) — design

**Status:** approved
**Date:** 2026-05-23
**Branch:** `chaayah` (stacked on `pluggable-curriculum`)
**Author:** PrevizKompany (with Claude)

## Problem

After the pluggable-curriculum refactor, forking long-way-engine still
requires forkers to edit `state.yaml` whenever they advance a module,
finish a book, take a vacation, or update a manual counter. This
contradicts the "set up once and forget" framing the README now
promises:

- `current_module` bumps every 2–6 weeks
- `books_state` flips at every book transition
- `paused` + `paused_since` + `pause_history` mutate at every break
- `manual_counters` need hand-editing for cosmetic dashboard updates
- `month` advances every 30 days (calendar-derivable but currently manual)

YAML edits are also error-prone — a forker who mistypes a book title
silently breaks the dashboard's books badge.

## Goal

Make state mutation flow through Todoist instead of `state.yaml`. After
fork setup, the user should never open `state.yaml` again. Specifically:

1. A weekly Todoist task with sub-task checkboxes is the primary
   surface for state changes (module advance, book transitions, planned
   pause, counter increments).
2. An always-on persistent pair of Todoist tasks (`Emergency pause` /
   `Resume`) handle unplanned breaks with ~24-hour latency.
3. `state.yaml` mutations are atomic, committed to git per cron run,
   and audited in an append-only `state_log.yaml`.
4. A first-class undo (`revert_last`) lets users unwind the most
   recent mutation by checking a box in the next weekly review.
5. `month` and `phase` derive from calendar elapsed time minus closed
   pause intervals — no longer user-edited.

## Non-goals

- LLM-parsed free-text responses. Comments are parsed only for integer
  counter values; otherwise checkbox completion is the signal.
- Multi-mutation undo. `revert_last` reverts one entry per check. Bulk
  unwinds use `git revert` of the cron commit.
- Per-user customization of the action vocabulary. Action types and
  `show_if` predicates are engine-defined; new ones require a code
  change. Sub-task titles and arguments are curriculum-author-defined.
- Real-time state mutation. All mutations have up to ~24h latency
  (next cron run). For sub-day latency, edit `state.yaml` directly
  (escape hatch).

## Architecture

### New files

```
src/
├── state_review.py             # orchestrates the state-mutation cron phase
├── state_mutations.py          # one pure function per action type
├── todoist_review.py           # TodoistReviewClient (read sub-tasks + comments)
state_log.yaml                  # append-only audit + undo source
```

### Modified files

```
src/todoist.py                  # add sub-task creation (parent_id) to TodoistClient
src/main.py                     # cron now: state-mutate → create → render
src/templates.py                # parse state_review + sub_tasks fields from YAML
src/state.py                    # derive month/phase from start_date + pause_history
config.yaml                     # add weekly_state_review to ritual_times
curriculum/rituals/weekly.yaml  # add weekly-state-review template
curriculum/manifest.yaml        # declare state_review_template_id + add
                                # weekly_state_review to ritual_times_required
examples/*/rituals/weekly.yaml  # add equivalent state-review templates
examples/*/manifest.yaml        # declare review template + ritual time
AGENTS.md                       # document state_review schema + interview Step 5.5
docs/FORKING.md                 # rewrite Step 10 (Maintenance) for new flow
README.md                       # one-line addendum to "Fork it" workflow
```

### Daily cron flow (new ordering)

```
1. Load config + state + syllabus, validate curriculum.
2. STATE-MUTATION PHASE (new):
   a. TodoistReviewClient: find last weekly-state-review task by external_id.
   b. Read its sub-tasks + completion + comments.
   c. Read persistent emergency-pause task; read resume task if paused.
   d. For each completed sub-task whose todoist_task_id is NOT already in
      state_log.yaml, apply its action via state_mutations dispatch.
   e. Write state.yaml atomically; append entries to state_log.yaml.
   f. Recreate consumed persistent tasks (emergency-pause, resume).
   g. Commit state.yaml + state_log.yaml to git (only if non-empty diff).
3. TASK-CREATION PHASE (existing):
   - Walk every template, evaluate cadence, create Todoist tasks idempotently.
   - For the state_review template: create parent + sub-tasks per declared list.
4. DASHBOARD PHASE (existing): regenerate docs/index.html + commit.
```

State-mutation runs FIRST so today's task creation reflects any
module advance / pause that happened yesterday.

### Pluggable boundary

| Surface | Defined in | Forker edits? |
| --- | --- | --- |
| Weekly-review template (title, day, sub-task list) | `curriculum/rituals/*.yaml` | yes |
| Sub-task titles + argument bindings | `curriculum/rituals/*.yaml` | yes |
| Action vocabulary (`advance_module`, etc.) | `src/state_mutations.py` | no — code change |
| `show_if` predicates | `src/state_review.py` | no — code change |
| Persistent pause/resume task content | `src/state_review.py` | no — engine built-in |
| Cron flow + idempotency check | `src/main.py` + `src/state_review.py` | no |

## Schemas

### `state_review` template

A normal ritual template with two new fields. At most one template per
curriculum may have `state_review: true`.

```yaml
- id: weekly-state-review
  title: "Weekly state review — {iso_year}-W{iso_week:02d}"
  description: |
    Check the sub-tasks that apply to your week.
  due: "today at {ritual_times.weekly_state_review}"
  labels: [weekly-ritual]
  cadence: weekly
  day_of_week: sunday

  state_review: true              # NEW: marks this as the review entry point

  sub_tasks:                       # NEW: list of sub-task specs
    - title: "I'm ready to advance to Module {next_module}"
      action: { type: advance_module }
      show_if: not_on_last_module    # optional gate

    - title: "I finished {current_book}"
      action: { type: mark_book_finished, book: "{current_book}" }

    - title: "Anki cards added this week (count in comment)"
      action: { type: increment_counter, counter: anki_card_count }

    - title: "Revert last week's state change (only if a mistake)"
      action: { type: revert_last }
```

Sub-task title placeholders use the same substitution engine as
parent-task titles (`{current_book}`, `{ritual_times.X}`, `{iso_year}`,
etc.) plus three new ones:

| Placeholder | Resolves to |
| --- | --- |
| `{next_module}` | `state.current_module + 1` |
| `{next_book}` | the book `primary_book_by_month[month+1]` if it differs from current, else "" |
| `{current_phase_name}` | `syllabus.phases[<for current month>].name` |

### Action vocabulary

| `type` | Args | Effect | Idempotent? |
| --- | --- | --- | --- |
| `advance_module` | — | `current_module += 1`; append previous to `completed_modules`. No-op if already on last module. | Per `todoist_task_id` |
| `mark_book_finished` | `book` (str) | `books_state[book] = done`. | Per task_id |
| `mark_book_started` | `book` (str) | `books_state[book] = current`. | Per task_id |
| `set_pause` | `days` (int), `reason` (str) | `paused: true`, `paused_since: today`. Auto-unpause on the first cron run after `paused_since + days <= today` (engine writes an `unset_pause` log entry with `todoist_task_id: "auto-unpause-<paused_since>"`). | Per task_id |
| `unset_pause` | — | Append open interval to `pause_history`, clear `paused_since`, `paused: false`. | Per task_id |
| `increment_counter` | `counter` (str) | Parse int from first comment on sub-task; `manual_counters[counter] += int`. Skip with warning if no comment, empty comment, or `int(comment.strip())` raises. | Per task_id |
| `revert_last` | — | Pop most recent non-revert entry from `state_log.yaml`; restore that entry's `prior` block into `state.yaml`. | Per task_id |

### `show_if` predicates

| Name | True when |
| --- | --- |
| `not_on_last_module` | `state.current_module < len(syllabus.modules)` |
| `book_transition_this_month` | `primary_book_by_month[month] != primary_book_by_month[month-1]`, treating the lookup as carry-forward; false on month 1 (no prior). |
| `not_paused` | `state.paused == false` |
| `paused` | `state.paused == true` |
| (none / omitted) | always show |

Sub-tasks with a false `show_if` are not created in Todoist that fire.

### Persistent emergency-pause / resume tasks

Engine-built-in. NOT curriculum templates. Defined in
`src/state_review.py`:

```python
EMERGENCY_PAUSE_TASK = {
    "external_id": "emergency-pause",
    "title": "🛑 Emergency pause (stops tasks on next cron)",
    "description": "Check this to pause immediately. Auto-recreates after consumption.",
    # No due date — persistent.
}

RESUME_TASK = {
    "external_id": "resume",
    "title": "▶️ Resume (only fires when paused)",
    "description": "Check this when you're back.",
    "show_if": "paused",  # only created when state.paused is true
}
```

The engine recreates each persistent task with a fresh `external_id`
suffix (e.g., `emergency-pause-<timestamp>`) after consumption, so each
"pause request" has a unique cache key. Idempotency holds: same
`todoist_task_id` produces at most one log entry.

### `state_log.yaml`

Append-only YAML sequence. One entry per applied mutation.

```yaml
- timestamp: 2026-06-07T06:00:00+05:30
  action: advance_module
  todoist_task_id: "8745321234"
  prior:
    current_module: 4
    completed_modules: [1, 2, 3]
  new:
    current_module: 5
    completed_modules: [1, 2, 3, 4]
  message: "advanced to module 5"

- timestamp: 2026-06-14T06:00:00+05:30
  action: revert_last
  todoist_task_id: "8745321410"
  reverted_entry_timestamp: 2026-06-07T06:00:00+05:30
  reverted_action: advance_module
  message: "reverted: current_module back to 4"
```

`revert_last` semantics:

- Pops the most recent NON-revert entry from `state_log.yaml`.
- Restores that entry's `prior` block into `state.yaml`.
- Writes a new log entry documenting the revert.
- The reverted entry stays in the log (never destroyed; audit complete).
- No-op with warning if log is empty.
- If the most recent entry is itself a revert, `revert_last` skips past it
  to the next non-revert entry (no re-reverting a revert).

### `state.yaml` changes

- `month` and `phase` become engine-managed. Engine writes them each
  cron run from `derive_month(state, today)` and `derive_phase(month,
  syllabus)`. Owner-set values are overwritten — they're computed, not
  authoritative.
- `current_module`, `current_book`, `paused`, `paused_since`,
  `pause_history`, `books_state`, `completed_modules`,
  `manual_counters` continue to be authoritative state, but written by
  the engine (via mutations) rather than the user.
- `start_date`, `timezone`, `notes`, `learning_tracks` remain
  user-editable (fork-setup or rare manual updates).

## Engine modules

### `src/todoist_review.py` (new)

Read-only. Strictly isolated from `TodoistClient` (write) and
`TodoistCompletionClient` (completion-window read). New session, new
retry helper, no shared private methods.

```python
class TodoistReviewClient:
    def __init__(self, token: str, project_id: str, ...): ...

    def get_subtasks(self, parent_task_id: str) -> list[Subtask]:
        """Returns list of subtasks under parent. Each Subtask has
        id, content, is_completed, comment_count."""

    def get_first_comment(self, task_id: str) -> str | None:
        """Returns text of the earliest comment on task_id, or None."""

    def find_task_by_external_id(self, external_id: str) -> str | None:
        """Resolves external_id (content marker) to live Todoist task_id.
        Reads the same project_id-scoped task list TodoistClient does."""
```

`Subtask` dataclass:

```python
@dataclass(frozen=True)
class Subtask:
    id: str
    content: str
    is_completed: bool
    comment_count: int
    parent_id: str
```

### `src/state_mutations.py` (new)

One pure function per action type. Each returns a `MutationResult`:

```python
@dataclass(frozen=True)
class MutationResult:
    new_state: State
    log_entry: dict
    user_message: str

def advance_module(state, syllabus, *, todoist_task_id, today) -> MutationResult: ...
def mark_book_finished(state, *, book, todoist_task_id, today) -> MutationResult: ...
def mark_book_started(state, *, book, todoist_task_id, today) -> MutationResult: ...
def set_pause(state, *, days, reason, todoist_task_id, today) -> MutationResult: ...
def unset_pause(state, *, todoist_task_id, today) -> MutationResult: ...
def increment_counter(state, *, counter, delta, todoist_task_id, today) -> MutationResult: ...
def revert_last(state, log_entries, *, todoist_task_id, today) -> MutationResult: ...
```

Dispatch table:

```python
ACTION_HANDLERS = {
    "advance_module": advance_module,
    "mark_book_finished": mark_book_finished,
    "mark_book_started": mark_book_started,
    "set_pause": set_pause,
    "unset_pause": unset_pause,
    "increment_counter": increment_counter,
    "revert_last": revert_last,
}
```

### `src/state_review.py` (new)

Orchestrates the state-mutation phase:

```python
def run_state_review_phase(
    *, config, state, syllabus, today, todoist_review, todoist_client,
    state_path, state_log_path,
) -> StateReviewSummary:
    """
    1. Find last fired weekly-state-review parent (by external_id from cache).
    2. Fetch its sub-tasks via TodoistReviewClient.
    3. Fetch the persistent emergency-pause + resume tasks.
    4. For each completed task NOT already in state_log: dispatch its action.
    5. Atomically write state.yaml + append to state_log.yaml.
    6. Recreate consumed persistent tasks via TodoistClient.
    7. Return summary (for cron logs + git commit message).
    """
```

The orchestrator never mutates state mid-flight — it builds the
full sequence of `MutationResult`s, then applies the final `new_state`
to disk atomically. If any single mutation raises, the orchestrator
logs the error, skips that action, and continues with the rest.

### `src/state.py` changes

```python
def derive_month(state: State, today: date) -> int:
    """Month from elapsed days minus closed pause intervals, /30 +1."""
    elapsed = (today - state.start_date).days
    paused_days = sum(
        (interval.end - interval.start).days
        for interval in state.pause_history
    )
    return ((elapsed - paused_days) // 30) + 1

def derive_phase(month: int, syllabus: Syllabus) -> int:
    for phase in syllabus.phases:
        if phase.months[0] <= month <= phase.months[1]:
            return phase.number
    return syllabus.phases[-1].number

def update_derived_fields(state: State, syllabus: Syllabus, today: date) -> State:
    """Replace state.month + state.phase with derivations. Called by cron."""
    month = derive_month(state, today)
    phase = derive_phase(month, syllabus)
    return replace(state, month=month, phase=phase)
```

### `src/templates.py` changes

Parser recognizes `state_review: true` and `sub_tasks: [...]` fields
on templates. The `Template` dataclass gains:

```python
state_review: bool = False
sub_tasks: list[SubtaskSpec] = field(default_factory=list)
```

```python
@dataclass(frozen=True)
class SubtaskSpec:
    title: str            # with placeholders
    action: dict          # {type: str, **args}
    show_if: str | None = None
```

### `src/todoist.py` changes

`TodoistClient.create_task_idempotent` gains an optional `parent_id`
arg. When set, the created task is a sub-task. Cache key is unchanged
(still keyed by external_id) — sub-tasks have their own external_id
content markers.

## Validation rules (added to `curriculum_validator.py`)

Three new checks aggregate alongside the existing 10:

11. At most ONE template across all `rituals/*.yaml` and `modules.yaml`
    may have `state_review: true`.
12. If a `state_review: true` template exists, its `cadence` must be
    `weekly`, and `day_of_week` must be set.
13. Every `sub_tasks[].action.type` must be in the action vocabulary.
    Every `sub_tasks[].show_if` (if present) must be in the predicate
    vocabulary.

## Idempotency strategy

The single biggest correctness concern. Same Todoist completion could
be observed multiple times if the cron runs twice in a day, or if a
manual re-run replays.

Pinned on `todoist_task_id`:

- Every `state_log.yaml` entry records the `todoist_task_id` that
  produced it (and for `revert_last`, the task_id of the REVERT, not
  the reverted entry).
- Before dispatching any action, the orchestrator checks: is this
  task_id already present in `state_log.yaml`? If yes, skip.
- For persistent tasks (`emergency-pause`, `resume`), the engine
  CONSUMES them by deleting + recreating with a new external_id. Each
  consumption has a unique task_id. Idempotency holds.

If `state_log.yaml` is somehow deleted (forker accident, repo reset),
the engine would re-apply every completion in the current Todoist
window. Mitigation: `state_log.yaml` is committed to git per cron
run; recovery is `git checkout HEAD~1 -- state_log.yaml`. Documented
in FORKING.md troubleshooting.

## Failure modes

- **Todoist read fails (rate limit, network).** Log warning, skip state
  phase, continue with task creation. State stays where it was.
- **Counter comment unparseable** (e.g., "around 8"). Log warning, skip
  that one counter, continue applying other mutations from the same
  review. Engine attempts `int(comment.strip())`; anything else fails.
- **state.yaml write fails after mutations applied to in-memory state.**
  Atomic write (`.tmp` + rename) prevents half-written file. If
  rename fails, no log entry written, mutation re-attempted on next
  cron (idempotency stays correct because we check log BEFORE applying).
- **Conflict between persistent pause and review-scheduled pause.**
  Both set `paused: true`. The second wins by overwrite, but the log
  records both attempts. Edge case but harmless.
- **User checks `revert_last` and `advance_module` in same review.**
  Order matters: applied in declaration order (top-to-bottom in the
  sub-task list). Convention: put `revert_last` LAST in the template,
  so it reverts the prior week — not anything checked this week.

## Testing strategy

- **Unit tests per `state_mutations` handler** with fixtures for state
  + assert MutationResult fields. Pure functions, no IO.
- **Validator tests** for the 3 new checks (broken fixtures per rule).
- **Idempotency test**: dispatch the same action twice with the same
  task_id, assert only one log entry + one state change.
- **End-to-end with mocked TodoistReviewClient**: simulate a week of
  sub-task completions, run the cron phase, assert state.yaml +
  state_log.yaml match expected post-state.
- **Derive-month/phase tests**: parametrize across pause-history
  configurations, assert correctness across phase boundaries.
- **Golden output**: the existing 9 dates still produce byte-identical
  capture output (the state-review template only fires on Sunday;
  derive-month equals the previous hardcoded month for those dates
  given the live state.yaml's start_date).

## Migration

For the OWNER's live engine: their existing `state.yaml` doesn't have
the `weekly-state-review` template. Three options:

1. Engine ships the new template in `curriculum/rituals/weekly.yaml`
   when this lands. First cron after merge creates the parent task on
   the next Sunday. No state.yaml changes; existing manual flow keeps
   working until the first review fires.
2. `state_log.yaml` starts empty; first mutation populates it.
3. `month` derivation overwrites `state.yaml`'s current value on first
   run. If the derived value differs from the current value, that's
   a real bug in the syllabus's month accounting — flag in cron logs,
   don't silently mutate. Tests assert derivation matches current
   value for the live state.yaml.

For FORKERS: the FORKING.md walkthrough now describes the review flow
as part of initial setup. They never see the manual-edit world.

## Open questions

None at design time. Concrete sub-task wording for the live curriculum
will be drafted during implementation; their exact text doesn't affect
the engine.
