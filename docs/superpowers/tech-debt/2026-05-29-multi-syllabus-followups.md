# Multi-syllabus refactor — tech debt follow-ups

**Date:** 2026-05-29
**Source:** cross-cutting review at end of `feature/multi-syllabus` branch
**Related:** [`docs/superpowers/specs/2026-05-28-multi-syllabus-design.md`](../specs/2026-05-28-multi-syllabus-design.md), [`docs/superpowers/plans/2026-05-28-multi-syllabus.md`](../plans/2026-05-28-multi-syllabus.md)

The 16-task multi-syllabus refactor shipped to `feature/multi-syllabus`
in a healthy state — 484/484 tests green, all smoke scripts exit clean.
But the cross-cutting review flagged six items the per-task agents
knowingly deferred or didn't catch. They're all real, none block merge,
and they're tracked here so they don't get lost.

## Important

### 1. `SyllabusState.manual_counters` is a ghost field

`SyllabusState` carries a `manual_counters: dict[str, Any]` field that
is loaded from `state/<key>.yaml` if present and used by `_practice_counts`
in `src/dashboard.py` to render the **per-syllabus** card's practice
tracker.

Two problems:

- `save_syllabus_state` does NOT write it back. Hand-editing
  `state/<key>.yaml` with `manual_counters:` causes the values to load,
  flash through one render cycle, then disappear on the next save.
- The shared `state/shared.yaml`'s `manual_counters` is the canonical
  home for user-life-wide counters (Anki, PRs, traces, pair sessions),
  and `render_multi_syllabus` already renders them in the shared header
  band. The per-syllabus duplicate is structurally redundant.

**Fix options:**

- (a) Remove the field from `SyllabusState`. Update `_practice_counts`
  in `dashboard.py` to read from a `shared: SharedState` argument the
  caller passes in. Update existing single-syllabus tests
  (`test_dashboard.py`'s `_partial_inputs`/`_full_inputs`/`_paused_inputs`)
  to construct a `SharedState` with the counter values.
- (b) Keep the field but make it round-trip correctly (`save_syllabus_state`
  writes `manual_counters: dict(state.manual_counters)`) and document
  what it's for. Reserved for a future use case where per-syllabus
  counters make sense (e.g., "PRs landed for this path's project").

(a) is cleaner; (b) preserves optionality. Choose at the next time we
touch the dashboard.

### 2. Scheduler kernel still uses legacy `State`

`src/scheduler.py`, `src/templates.py`, and `src/tracks.py` still declare
`state: State` in their function signatures and read fields off the
legacy `State` dataclass. The multi-syllabus loop in `src/main.py` works
because:

- `run_for_syllabus` synthesizes a per-syllabus `Config` shim from
  `MultiSyllabusConfig + SyllabusEntry` and passes it through.
- `SyllabusState` and `State` share enough field names (`current_module`,
  `current_book`, `phase`, `month`, `start_date`, `pause_history`, etc.)
  that duck typing succeeds.

This is fragile in two ways:

- New per-syllabus fields on `SyllabusState` that don't exist on `State`
  (or vice versa) will break silently.
- Static type checkers (mypy, pyright) flag every call site.

**Fix:** retype `should_create_today`, `resolve_variables`,
`compute_lifecycle_transitions`, and `evaluate_gates` to `SyllabusState`.
Remove the `Config` shim from `run_for_syllabus` by passing the fields
those callees actually need (`ritual_times`, `sunday_off`, `pair_day`)
as explicit arguments. Then drop the `Config` dataclass and `State`
dataclass entirely.

This is the last unfinished step from the original plan's "Task 12
removes the old" promise.

### 3. `STATE_PATH = REPO_ROOT / "state.yaml"` lingers in `main.py`

`src/main.py` still defines `STATE_PATH = REPO_ROOT / "state.yaml"` at
the module level as a "legacy fallback so test monkeypatches still
work." `state.yaml` doesn't exist anymore. The legacy `run()` function
uses it as a default for the `state_path` parameter; if any caller
invokes `run()` without overriding `state_path`, it gets
`FileNotFoundError` rather than a graceful error.

**Fix:** when the legacy `State`/`Config`/`load_state`/`save_state`
shims go (item 2 above), the legacy `run()` function and `STATE_PATH`
constant go with them. Until then, set `STATE_PATH = None` or remove
the constant; any caller depending on the implicit default should fail
loudly at import.

## Minor

### 4. AGENTS.md still mentions `state.yaml` in a few snippets

The T16 doc pass updated the main path references but missed a few
inline YAML examples in the state-review template section (around
lines 328, 330, 363, 395 at the time of this writing). A forker
following the guide will see references to a single-file `state.yaml`
that no longer matches reality.

**Fix:** one-pass edit replacing `state.yaml` with `state/<name>.yaml`
in those inline examples.

### 5. `state.py` module docstring describes the old layout

`src/state.py`'s top-of-file docstring (lines 1–18) describes the Phase
A–E evolution of a single-file `state.yaml`. It was not updated when
the file got `SharedState` + `SyllabusState` + their loaders.

**Fix:** rewrite the docstring to describe the current split:

- `SharedState` holds user-life-wide fields (timezone, manual_counters,
  notes) loaded from `state/shared.yaml`.
- `SyllabusState` holds per-syllabus fields loaded from
  `state/<key>.yaml`.
- The legacy `State` exists only as a transitional shim and will be
  removed alongside `load_state`/`save_state`.

### 6. Committed `docs/index.html` is pre-refactor format

The HTML at `docs/index.html` on `main` is the artifact from the
2026-05-28 cron run, which used the single-card layout. Anyone visiting
the GitHub Pages site between merge and the next post-merge cron will
see the old format.

**Fix:** none required — the next cron run after merge regenerates
`docs/index.html` in the new multi-syllabus shape. Alternative: trigger
one `workflow_dispatch` after merge to pre-warm the page.

## Tracking

These items should be picked up before:

- Adding a second syllabus (items 1, 2 will compound — a second
  syllabus with different module/book pointer semantics is exactly the
  case where the legacy `State` duck-typing breaks).
- The next significant `src/main.py` or `src/state.py` change (items
  2, 3, 5 cluster together).

Items 4 and 6 are independent and can be picked off any time.
