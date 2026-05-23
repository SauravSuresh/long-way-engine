"""Curriculum-declared learning tracks: gate predicates + lifecycle.

This module is the runtime read path for the `tracks:` section
declared in `curriculum/syllabus.yaml`. Validation lives in
`src/curriculum_validator.py`.

Two surfaces:

  1. `evaluate_gates(template_gated_by, state)` — invoked by the
     scheduler. Returns (passes, skip_reason). Each gate is a
     tagged dict (`{"type": ..., ...}`) from a template's
     `gated_by:` list. Locked-vocabulary dispatch — adding a new
     gate type is a code change here.

  2. `compute_lifecycle_transitions(state, tracks, derived_month,
     applied_task_ids)` — invoked by the state-review orchestrator
     between auto-unpause and the sub-task scan. Returns the list
     of LifecycleTransitions the engine should apply, per the
     conflict rules pinned in the spec
     (docs/superpowers/specs/2026-05-23-curriculum-tracks-design.md).

Both functions are pure: no IO, no clock, no syllabus mutation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.state import State
from src.syllabus import TrackDeclaration


@dataclass(frozen=True)
class LifecycleTransition:
    category: str
    title: str
    from_state: str
    to_state: str
    todoist_task_id: str
    month: int


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slug_of(category: str, title: str) -> str:
    """Stable, filesystem-friendly slug for a (category, title) pair.

    Lowercased; non-alphanumerics collapsed to single hyphens; leading
    and trailing hyphens stripped. Used inside synthetic
    todoist_task_ids for auto-lifecycle transitions so the same
    transition produces the same id across replays.
    """
    raw = f"{category}-{title}".lower()
    return _SLUG_NON_ALNUM.sub("-", raw).strip("-")


# --- gate predicates --------------------------------------------------------


def evaluate_gates(
    gated_by: list[dict],
    state: State,
) -> tuple[bool, str | None]:
    """AND-evaluate every gate in `gated_by` against `state`.

    Returns (True, None) if every gate passes (or the list is empty).
    On first failure: (False, "<human reason>"). Unknown gate types
    fall through as failure with a defensive log path — validator
    rule 17 should have caught the curriculum at startup.
    """
    if not gated_by:
        return True, None
    for gate in gated_by:
        gtype = gate.get("type") if isinstance(gate, dict) else None
        if gtype == "track":
            if not _track_gate_passes(gate, state):
                cat = gate.get("category")
                item = gate.get("item")
                states = gate.get("states") or ["current"]
                return False, f"gated: track ({cat!r}, {item!r}) not in {states!r}"
        elif gtype == "module_eq":
            if state.current_module != int(gate.get("value", -1)):
                return False, f"gated: current_module != {gate.get('value')}"
        elif gtype == "module_gte":
            if state.current_module < int(gate.get("value", 1 << 30)):
                return False, f"gated: current_module < {gate.get('value')}"
        elif gtype == "module_lte":
            if state.current_module > int(gate.get("value", -1)):
                return False, f"gated: current_module > {gate.get('value')}"
        else:
            return False, f"gated: unknown gate type {gtype!r}"
    return True, None


def _track_gate_passes(gate: dict, state: State) -> bool:
    category = gate.get("category")
    item = gate.get("item")
    if category is None or item is None:
        return False
    allowed = gate.get("states") or ["current"]
    if isinstance(allowed, str):
        allowed = [allowed]
    actual = state.learning_tracks.get(str(category), {}).get(str(item))
    return actual in allowed


# --- lifecycle --------------------------------------------------------------


def expected_position(decl: TrackDeclaration, derived_month: int) -> str:
    """Map a derived month to one of:
      - 'pre_start' : month before the declared start
      - 'current'   : month inside [start, end]
      - 'past_end'  : month after the declared end
    Declarations without `months` always return 'pre_start' (manual
    lifecycle — engine never auto-transitions them).
    """
    if decl.months is None:
        return "pre_start"
    start, end = decl.months
    if derived_month < start:
        return "pre_start"
    if derived_month <= end:
        return "current"
    return "past_end"


def compute_lifecycle_transitions(
    state: State,
    tracks: list[TrackDeclaration],
    derived_month: int,
    applied_task_ids: set[str],
) -> list[LifecycleTransition]:
    """Per the conflict-rule table in the spec, return only the
    transitions the engine should apply right now.

    Rules:
      - owner state always wins on a tie (no-op);
      - `not_started` → `current` only when expected == 'current';
      - `current` → `done` only when expected == 'past_end';
      - `not_started` past `end` STAYS not_started (no skipped state);
      - `done` never re-opens;
      - any transition whose synthetic todoist_task_id is already in
        `applied_task_ids` is skipped (idempotency).
    """
    transitions: list[LifecycleTransition] = []
    for decl in tracks:
        if decl.months is None:
            continue
        expected = expected_position(decl, derived_month)
        actual = state.learning_tracks.get(decl.category, {}).get(decl.title, "not_started")

        if actual == "not_started" and expected == "current":
            task_id = _auto_task_id(decl, side="start", month=decl.months[0])
            if task_id in applied_task_ids:
                continue
            transitions.append(LifecycleTransition(
                category=decl.category,
                title=decl.title,
                from_state=actual,
                to_state="current",
                todoist_task_id=task_id,
                month=decl.months[0],
            ))
        elif actual == "current" and expected == "past_end":
            task_id = _auto_task_id(decl, side="end", month=decl.months[1])
            if task_id in applied_task_ids:
                continue
            transitions.append(LifecycleTransition(
                category=decl.category,
                title=decl.title,
                from_state=actual,
                to_state="done",
                todoist_task_id=task_id,
                month=decl.months[1],
            ))
        # All other (owner_state, expected) combinations: no-op per spec.
    return transitions


def _auto_task_id(decl: TrackDeclaration, *, side: str, month: int) -> str:
    return f"auto-track-{slug_of(decl.category, decl.title)}-{side}-{month}"
